import logging
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, Field

from app import codeforces
from app.codeforces import Contest, Submission

log = logging.getLogger("autoprogcomp-logic")


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
    by_handle: list[str | int]


CommandOutputGenerator = Callable[[GlobalState], CommandOutput]
CommandParser = Callable[["Commands", re.Match[str]], CommandOutputGenerator | None]


class ContestCmd(BaseModel):
    contest_id: str
    points_by_index: dict[re.Pattern[str], int]

    @staticmethod
    def new(c: "Commands", contest_id: str, points_mapping: str | None) -> CommandOutputGenerator:
        points_by_index: dict[re.Pattern[str], int] = {}
        if points_mapping is None:
            points_by_index[re.compile(r".*")] = 1
        else:
            for mapping in points_mapping.split(","):
                mapping_mat = re.fullmatch(r"([^=]+)=(\d+)", mapping)
                if mapping_mat is None:
                    raise RuntimeError(f"invalid problem point mapping '{mapping}'")
                pat = re.compile(mapping_mat[1], re.IGNORECASE)
                points_by_index[pat] = int(mapping_mat[2])
        cmd = ContestCmd(contest_id=contest_id, points_by_index=points_by_index)
        c.contest.append(cmd)
        return cmd.generate_output

    @staticmethod
    def parse_from_id(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        return ContestCmd.new(c, mat[1], mat[2])

    @staticmethod
    def parse_from_group_and_time(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator | None:
        group_id, start, end, points_mapping = mat
        start = datetime.fromisoformat(start)
        end = datetime.fromisoformat(end)

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
            t = datetime.fromtimestamp(t)
            if t < start or t > end:
                continue
            if t - start < cur_delta:
                contest_id = str(contest.id)
                cur_delta = t - start
        if contest_id is None:
            log.warning("no contest found for group %s and timerange %s to %s, skipping", group_id, start, end)
            return None

        return ContestCmd.new(c, contest_id, points_mapping)

    def compute_points(self, global_state: GlobalState):
        for handle_state in global_state.by_handle.values():
            contest = handle_state.by_contest.get(self.contest_id, None)
            if contest is not None:
                for index, sub in contest.by_index.items():
                    if sub.verdict == "OK":
                        for pat, points in self.points_by_index.items():
                            if pat.fullmatch(index):
                                if sub.author.participantType == "CONTESTANT":
                                    sub.synthetic.points = max(sub.synthetic.points or 0, points)
                                else:
                                    sub.synthetic.points_with_coupon = max(
                                        sub.synthetic.points_with_coupon or 0, points
                                    )

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
        start = datetime.fromisoformat(mat[1])
        end = datetime.fromisoformat(mat[2])
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
    timeframe: TimeframeCmd = TimeframeCmd(start=datetime.now(), end=datetime.now(), valid=False)


COMMANDS: dict[re.Pattern[str], CommandParser] = {
    re.compile(r"^contest:(\d+)(?::(.+))?$"): ContestCmd.parse_from_id,
    re.compile(r"^contest:([^:]+):([^:]+):([^:]+):(?::(.+))?$"): ContestCmd.parse_from_group_and_time,
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
                if output_generator is not None:
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
        submissions = codeforces.contest_status(contest.contest_id)
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

    # Apply coupons
    if commands.coupons:
        commands.coupons.apply_coupons(global_state)

    # Compute points for each problem
    for cmd in commands.contest:
        cmd.compute_points(global_state)

    # Generate final output
    output: list[CommandOutput] = []
    for generator in output_generators:
        output.append(generator(global_state))
    return output
