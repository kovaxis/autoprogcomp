import re
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel, Field

from app import codeforces
from app.codeforces import Submission


class ContestState(BaseModel):
    rated_name: str | None = None
    by_index: dict[str, Submission] = Field(default_factory=dict)


class HandleState(BaseModel):
    by_contest: defaultdict[str, ContestState] = Field(default_factory=lambda: defaultdict(ContestState))
    available_coupons: int = 0
    used_coupons: int = 0


class GlobalState(BaseModel):
    handles: list[str]
    by_handle: defaultdict[str, HandleState] = Field(default_factory=lambda: defaultdict(HandleState))


class CommandOutput(BaseModel):
    by_handle: list[str]


CommandOutputGenerator = Callable[[GlobalState], CommandOutput]
CommandParser = Callable[["Commands", re.Match[str]], CommandOutputGenerator]


class ContestCmd(BaseModel):
    contest_id: str
    points_by_index: dict[re.Pattern[str], int]

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        points_by_index: dict[re.Pattern[str], int] = {}
        for mapping in mat[2].split(","):
            mapping_mat = re.fullmatch(r"([^=]+)=(\d+)", mapping)
            if mapping_mat is None:
                raise RuntimeError(f"invalid problem point mapping '{mapping}'")
            pat = re.compile(mapping_mat[1], re.IGNORECASE)
            points_by_index[pat] = int(mapping_mat[2])
        cmd = ContestCmd(contest_id=mat[1], points_by_index=points_by_index)
        c.contest.append(cmd)
        return cmd.generate_output

    def compute_points(self, global_state: GlobalState):
        for handle_state in global_state.by_handle.values():
            contest = handle_state.by_contest.get(self.contest_id, None)
            if contest is not None:
                for index, sub in contest.by_index.items():
                    if sub.verdict == "OK":
                        for pat, points in self.points_by_index.items():
                            if pat.fullmatch(index):
                                sub.synthetic.points = max(sub.synthetic.points or 0, points)
                                if sub.author.participantType != "CONTESTANT":
                                    sub.synthetic.requires_coupon = True

    def generate_output(self, global_state: GlobalState) -> CommandOutput:
        out = CommandOutput(by_handle=[])
        for handle in global_state.handles:
            handle_state = global_state.by_handle[handle]
            score = 0
            subs_that_require_coupon: list[int] = []
            for contest in handle_state.by_contest.values():
                for sub in contest.by_index.values():
                    if sub.synthetic.points is not None:
                        if sub.synthetic.requires_coupon:
                            subs_that_require_coupon.append(sub.synthetic.points)
                        else:
                            score += sub.synthetic.points
            subs_that_require_coupon.sort(reverse=True)
            handle_state.used_coupons = min(len(subs_that_require_coupon), handle_state.available_coupons)
            score += sum(subs_that_require_coupon[: handle_state.used_coupons])
            out.by_handle.append(str(score))
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
                    if self.lang in sub.programmingLanguage.lower():
                        solved_with_lang += 1
            out.by_handle.append(str(solved_with_lang))
        return out


class CouponCmd(BaseModel):
    available_coupons: int

    @staticmethod
    def parse(c: "Commands", mat: re.Match[str]) -> CommandOutputGenerator:
        if c.coupons:
            raise RuntimeError("at most 1 coupons command can be specified")
        c.coupons = CouponCmd(available_coupons=int(mat[1]))
        return c.coupons.generate_output

    def assign_coupons(self, global_state: GlobalState):
        for handle_state in global_state.by_handle.values():
            handle_state.available_coupons = self.available_coupons

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
            out.by_handle.append(str(count))
        return out


class Commands(BaseModel):
    contest: list[ContestCmd] = []
    lang: list[LangCmd] = []
    coupons: CouponCmd | None = None
    rounds: list[RoundCmd] = []


COMMANDS: dict[re.Pattern[str], CommandParser] = {
    re.compile(r"^contest:(\d+):(.+)$"): ContestCmd.parse,
    re.compile(r"^lang:(.+)$"): LangCmd.parse,
    re.compile(r"^coupons:(\d+)$"): CouponCmd.parse,
    re.compile(r"^rounds:(.+)$"): CouponCmd.parse,
    # TODO: Filter by submission time
}


def rank_submission(sub: Submission | None) -> int:
    """
    If there are multiple submissions to a problem, decide which one is more important based on this criteria.
    The largest rank overrides smaller ranks.
    Ties are broken by submission ID (newer submission override older ones).
    """
    if sub is None:
        return 0
    if sub.verdict == "OK":
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

    # Fetch user submissions
    global_state = GlobalState(handles=handles)
    for handle in handles:
        for submission in codeforces.user_status(handle):
            contest_id = "" if submission.contestId is None else str(submission.contestId)
            contest = global_state.by_handle[handle].by_contest[contest_id]
            prev = contest.by_index.get(submission.problem.index, None)
            if rank_submission(submission) > rank_submission(prev):
                contest.by_index[submission.problem.index] = submission

    # Fetch rated contests
    if commands.rounds:
        for handle in handles:
            ratings = codeforces.user_rating(handle)
            for rating in ratings:
                contest_id = str(rating.contestId)
                global_state.by_handle[handle].by_contest[contest_id].rated_name = rating.contestName

    # Assign coupons
    if commands.coupons:
        commands.coupons.assign_coupons(global_state)

    # Compute points for each problem
    for cmd in commands.contest:
        cmd.compute_points(global_state)

    # Generate final output
    output: list[CommandOutput] = []
    for generator in output_generators:
        output.append(generator(global_state))
    return output
