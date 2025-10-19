import logging
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import json5
from pydantic import BaseModel, Field, StringConstraints

from app import codeforces
from app.codeforces import CodeforcesException, Contest, Submission
from app.settings import config

log = logging.getLogger("autoprogcomp")


class ContestState(BaseModel):
    rated_name: str | None = None
    by_index: dict[str, Submission] = Field(default_factory=dict)


class HandleState(BaseModel):
    by_contest: defaultdict[str, Annotated[ContestState, Field(default_factory=ContestState)]] = Field(
        default_factory=lambda: defaultdict(ContestState)
    )
    available_coupons: int = 0
    used_coupons: int = 0

    def insert_submission(self, submission: Submission, commands: "Commands"):
        contest_id = "" if submission.contestId is None else str(submission.contestId)
        contest = self.by_contest[contest_id]
        prev = contest.by_index.get(submission.problem.index, None)
        if rank_submission(commands, submission) > rank_submission(commands, prev):
            contest.by_index[submission.problem.index] = submission


class GlobalState(BaseModel):
    handles: list[str]
    by_handle: defaultdict[str, Annotated[HandleState, Field(default_factory=HandleState)]] = Field(
        default_factory=lambda: defaultdict(HandleState)
    )


class CommandOutput(BaseModel):
    by_handle: list[str | int | None]


CommandOutputGenerator = Callable[[GlobalState], CommandOutput]
CommandParser = Callable[["Commands", re.Match[str]], CommandOutputGenerator]


def generate_empty_output(global_state: GlobalState) -> CommandOutput:
    return CommandOutput(by_handle=[None for _handle in global_state.handles])


class ContestCmd(BaseModel):
    class PointMapping(BaseModel):
        timerange: tuple[int, int] | None
        list_of_teams: list[set[str]] = []
        teams_by_handle: dict[str, list[set[str]]] = {}
        "Only give points to people on a team."
        whitelist_teams: bool
        mapping: dict[re.Pattern[str], int]

        @staticmethod
        def new(
            timerange: tuple[int, int] | None, mapping: dict[str, int], teams: list[list[str]] | None
        ) -> "ContestCmd.PointMapping":
            # Compile patterns
            compiled: dict[re.Pattern[str], int] = {}
            for pat, delta in mapping.items():
                compiled[re.compile(pat, re.IGNORECASE)] = delta

            # Collate teams
            list_of_teams = [set(team) for team in (teams or [])]
            teams_by_handle: dict[str, list[set[str]]] = {}
            for team in list_of_teams:
                for member in team:
                    teams_by_handle.setdefault(member, []).append(team)

            return ContestCmd.PointMapping(
                timerange=timerange,
                list_of_teams=list_of_teams,
                teams_by_handle=teams_by_handle,
                mapping=compiled,
                whitelist_teams=teams is not None,
            )

    class VisitedSubmission(BaseModel):
        ok: bool
        in_time: bool

        handle: str
        handle_state: HandleState
        contest: ContestState
        index: str
        sub: Submission
        point_mapping: "ContestCmd.PointMapping"
        pattern: re.Pattern[str]
        points: int

    contest_id: str
    point_mappings: list[PointMapping]

    class JsonInput(BaseModel):
        class JsonInputPoints(BaseModel):
            range: tuple[int, int] | None = None
            teams: list[list[str]] | None = None
            points: dict[str, int]

        id: Annotated[str, StringConstraints(pattern=r"\d+", max_length=12)] | None = None
        group: Annotated[str, StringConstraints(pattern=r"[0-9a-zA-Z]+", max_length=12)] | None = None
        time: str | tuple[str, str] | None = None
        points: dict[str, int] | list[JsonInputPoints]

    @staticmethod
    def parse_from_json5(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        # Parse raw JSON5
        try:
            raw = ContestCmd.JsonInput.model_validate(json5.loads(mat[1]))

            # Parse contest ID or get it from group ID + timerange
            if raw.id is not None:
                if raw.group is not None or raw.time is not None:
                    raise RuntimeError("id field is incompatible with group and time")
                contest_id = raw.id
            elif raw.group is not None:
                if raw.time is None:
                    raise RuntimeError("group field requires time field to be present")
                elif isinstance(raw.time, str):
                    start = datetime.fromisoformat(raw.time).astimezone(config.timezone)
                    end = start + timedelta(days=1)
                else:
                    start = datetime.fromisoformat(raw.time[0]).astimezone(config.timezone)
                    end = datetime.fromisoformat(raw.time[1]).astimezone(config.timezone)
                contest_id = ContestCmd.id_from_group_and_time(c, raw.group, start, end)
                if contest_id is None:
                    log.warning("no contest found for group %s and timerange %s to %s, skipping", raw.group, start, end)
                    return generate_empty_output
            else:
                raise RuntimeError("expected either id field or group field to be set")

            # Parse points
            points: list[ContestCmd.PointMapping]
            if isinstance(raw.points, dict):
                points = [ContestCmd.PointMapping.new(None, raw.points, [])]
            else:
                points = [
                    ContestCmd.PointMapping.new(
                        points.range,
                        points.points,
                        points.teams,
                    )
                    for points in raw.points
                ]

            # Build command
            cmd = ContestCmd(contest_id=contest_id, point_mappings=points)
            c.contest.append(cmd)
            return cmd.generate_output
        except Exception as e:
            raise RuntimeError(f'failed to parse contest command "{mat[0]}": {e}') from e

    @staticmethod
    def id_from_group_and_time(c: "Commands", group_id: str, start: datetime, end: datetime) -> str | None:
        contests_for_group = c.contests_by_group.get(group_id, None)
        if contests_for_group is None:
            contests_for_group = {str(contest.id): contest for contest in codeforces.contest_list(group_code=group_id)}
            c.contests_by_group[group_id] = contests_for_group

        contest_id = None
        cur_delta = timedelta.max
        for contest in contests_for_group.values():
            t = contest.startTimeSeconds
            if t is None:
                continue
            t = datetime.fromtimestamp(t, config.timezone)
            if t < start or t > end:
                continue
            if t - start < cur_delta:
                contest_id = str(contest.id)
                cur_delta = t - start

        return contest_id

    def visit_all_submissions(self, global_state: GlobalState, visit: Callable[[VisitedSubmission], None]):
        for handle, handle_state in global_state.by_handle.items():
            contest = handle_state.by_contest.get(self.contest_id, None)
            if contest is not None:
                for index, sub in contest.by_index.items():
                    for point_mapping in self.point_mappings:
                        if point_mapping.timerange is not None:
                            ok = (
                                sub.relativeTimeSeconds is not None
                                and point_mapping.timerange[0] * 60
                                <= sub.relativeTimeSeconds
                                <= point_mapping.timerange[1] * 60
                            )
                            if not ok:
                                continue
                        if point_mapping.whitelist_teams and handle not in point_mapping.teams_by_handle:
                            continue
                        for pat, points in point_mapping.mapping.items():
                            if pat.fullmatch(index):
                                visit(
                                    ContestCmd.VisitedSubmission(
                                        ok=sub.verdict == "OK",
                                        in_time=sub.author.participantType == "CONTESTANT",
                                        handle=handle,
                                        handle_state=handle_state,
                                        contest=contest,
                                        index=index,
                                        sub=sub,
                                        point_mapping=point_mapping,
                                        pattern=pat,
                                        points=points,
                                    )
                                )

    def share_team_submissions(self, global_state: GlobalState, commands: "Commands"):
        def visit(info: ContestCmd.VisitedSubmission):
            if info.ok and info.in_time:
                teams = info.point_mapping.teams_by_handle.get(info.handle, None)
                if teams:
                    for team in teams:
                        for teammate_handle in team:
                            teammate = global_state.by_handle.get(teammate_handle, None)
                            if teammate is not None:
                                teammate.insert_submission(info.sub, commands)

        self.visit_all_submissions(global_state, visit)

    def compute_points(self, global_state: GlobalState):
        def visit(info: ContestCmd.VisitedSubmission):
            if info.ok:
                if info.in_time:
                    info.sub.synthetic.points = max(info.sub.synthetic.points or 0, info.points)
                else:
                    info.sub.synthetic.points_with_coupon = max(info.sub.synthetic.points_with_coupon or 0, info.points)

        self.visit_all_submissions(global_state, visit)

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            score = 0
            contest = handle_state.by_contest.get(self.contest_id, None)
            if contest is not None:
                for sub in contest.by_index.values():
                    score += sub.synthetic.points or 0
            out.by_handle.append(score)
        return out


class LangCmd(BaseModel):
    lang: str

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        cmd = LangCmd(lang=mat[1].lower())
        c.lang.append(cmd)
        return cmd.generate_output

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            solved_with_lang = 0
            for contest in handle_state.by_contest.values():
                for sub in contest.by_index.values():
                    if sub.verdict == "OK" and self.lang in sub.programmingLanguage.lower():
                        solved_with_lang += 1
            out.by_handle.append(solved_with_lang)
        return out


class CouponCmd(BaseModel):
    available_coupons: int

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        if c.coupons:
            raise RuntimeError("at most 1 coupons command can be specified")
        c.coupons = CouponCmd(available_coupons=int(mat[1]))
        return c.coupons.generate_output

    def apply_coupons(self, global_state: GlobalState):
        for handle_state in global_state.by_handle.values():
            coupon_submissions: list[Submission] = []
            for contest in handle_state.by_contest.values():
                for submission in contest.by_index.values():
                    if submission.synthetic.points_with_coupon is not None:
                        coupon_submissions.append(submission)
            coupon_submissions.sort(key=lambda sub: sub.synthetic.points_with_coupon or 0, reverse=True)

            handle_state.available_coupons = self.available_coupons
            handle_state.used_coupons = min(len(coupon_submissions), self.available_coupons)
            for sub in coupon_submissions[: handle_state.used_coupons]:
                sub.synthetic.points = sub.synthetic.points_with_coupon

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            out.by_handle.append(f"{handle_state.used_coupons}/{handle_state.available_coupons}")
        return out


class RoundCmd(BaseModel):
    pattern: re.Pattern[str]

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        pat = re.compile(mat[1])
        cmd = RoundCmd(pattern=pat)
        c.rounds.append(cmd)
        return cmd.generate_output

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            count = 0
            for contest in handle_state.by_contest.values():
                if contest.rated_name is not None and self.pattern.fullmatch(contest.rated_name):
                    for sub in contest.by_index.values():
                        if sub.verdict == "OK" and sub.author.participantType == "CONTESTANT":
                            count += 1
            out.by_handle.append(count)
        return out


class TimeframeCmd(BaseModel):
    start: datetime
    end: datetime
    valid: bool

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        if c.timeframe.valid:
            raise RuntimeError("exactly 1 timeframe command must be specified")
        start = datetime.fromisoformat(mat[1]).astimezone(config.timezone)
        end = datetime.fromisoformat(mat[2]).astimezone(config.timezone)
        c.timeframe = TimeframeCmd(start=start, end=end, valid=True)
        return c.timeframe.generate_output

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            submission_count = 0
            for contest in handle_state.by_contest.values():
                for sub in contest.by_index.values():
                    if sub.verdict == "OK":
                        submission_count += 1
            out.by_handle.append(f"{submission_count} OK submissions")
        return out


class Commands(BaseModel):
    contests_by_group: dict[str, dict[str, Contest]] = {}

    contest: list[ContestCmd] = []
    lang: list[LangCmd] = []
    coupons: CouponCmd | None = None
    rounds: list[RoundCmd] = []
    timeframe: TimeframeCmd = TimeframeCmd(start=datetime.now(UTC), end=datetime.now(UTC), valid=False)


COMMANDS: dict[re.Pattern[str], CommandParser] = {
    re.compile(r"^contest:(.+)$"): ContestCmd.parse_from_json5,
    re.compile(r"^lang:(.+)$"): LangCmd.parse,
    re.compile(r"^coupons:(\d+)$"): CouponCmd.parse,
    re.compile(r"^rounds:(.+)$"): RoundCmd.parse,
    re.compile(r"^timeframe:([^:]+):([^:]+)$"): TimeframeCmd.parse,
}


def rank_submission(commands: Commands, sub: Submission | None) -> int:
    """
    If there are multiple submissions to a problem, decide which one is more important based on this criteria.
    The largest rank overrides smaller ranks.
    Ties are broken by submission ID (newer submission override older ones).
    """
    # Empty submissions have 0 priority
    if sub is None:
        return 0
    # Out-of-timeframe submissions have negative priority (ie. they don't even count)
    if (
        sub.creationTimeSeconds is None
        or sub.creationTimeSeconds < commands.timeframe.start.timestamp()
        or sub.creationTimeSeconds > commands.timeframe.end.timestamp()
    ):
        return -1
    # OK submissions have higher priority
    if sub.verdict == "OK":
        # In-contest submissions have higher priority than practice and virtual submissions
        if sub.author.participantType == "CONTESTANT":
            return 3
        else:
            return 2
    else:
        return 1


def compute(raw_commands: list[str], handles: list[str]) -> list[CommandOutput]:
    # Parse commands
    commands = Commands()
    output_generators: list[CommandOutputGenerator] = []
    for raw_cmd in raw_commands:
        for pat, parser in COMMANDS.items():
            mat = pat.fullmatch(raw_cmd)
            if mat:
                output_generator = parser(commands, mat)
                output_generators.append(output_generator)
                break
        else:
            raise RuntimeError(f"unrecognized command '{raw_cmd}'")
    if not commands.timeframe.valid:
        raise RuntimeError("a timeframe command must be provided!")
    global_state = GlobalState(handles=handles)

    # Fetch user submissions
    for handle in handles:
        global_state.by_handle[handle]
        for submission in codeforces.user_status(handle):
            global_state.by_handle[handle].insert_submission(submission, commands)

    # Fetch specific contest submissions
    seen_contests = {
        contest_id for handle_state in global_state.by_handle.values() for contest_id in handle_state.by_contest.keys()
    }
    for contest in commands.contest:
        if contest.contest_id in seen_contests:
            continue
        try:
            submissions = codeforces.contest_status(contest.contest_id)
        except CodeforcesException as e:
            if "has not started" in str(e):
                print(f"WARNING: {e}")
                continue
            raise e
        for submission in submissions:
            if len(submission.author.members) != 1:
                continue
            handle = submission.author.members[0].handle
            handle_state = global_state.by_handle.get(handle, None)
            if handle_state is not None:
                handle_state.insert_submission(submission, commands)

    # Fetch rated contests
    if commands.rounds:
        for handle in handles:
            ratings = codeforces.user_rating(handle)
            for rating in ratings:
                contest_id = str(rating.contestId)
                global_state.by_handle[handle].by_contest[contest_id].rated_name = rating.contestName

    # Share OK submissions between members of a team, within the contests that they are teams in
    for cmd in commands.contest:
        cmd.share_team_submissions(global_state, commands)

    # Compute points for each problem
    for cmd in commands.contest:
        cmd.compute_points(global_state)

    # Apply coupons
    if commands.coupons:
        commands.coupons.apply_coupons(global_state)

    # Generate final output
    output: list[CommandOutput] = []
    for generator in output_generators:
        output.append(generator(global_state))
    return output
