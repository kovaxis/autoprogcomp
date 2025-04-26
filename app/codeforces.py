import logging
import random
import time
from hashlib import sha512
from typing import Generic, Literal, TypeVar
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.settings import config
from app.synthetic import SubmissionSynthetic

log = logging.getLogger("codeforces")


class Problem(BaseModel):
    contestId: int | None = None
    problemsetName: str | None = None
    index: str
    name: str
    type: Literal["PROGRAMMING", "QUESTION"]
    points: float | None = None
    rating: int | None = None
    tags: list[str]


class Member(BaseModel):
    handle: str
    name: str | None = None


class Party(BaseModel):
    contestId: int | None = None
    members: list[Member]
    participantType: Literal["CONTESTANT", "PRACTICE", "VIRTUAL", "MANAGER", "OUT_OF_COMPETITION"]
    teamId: int | None = None
    teamName: str | None = None
    ghost: bool
    room: int | None = None
    startTimeSeconds: int | None = None


class Submission(BaseModel):
    id: int
    contestId: int | None = None
    creationTimeSeconds: int | None = None
    relativeTimeSeconds: int | None = None
    problem: Problem
    author: Party
    programmingLanguage: str
    verdict: (
        Literal[
            "FAILED",
            "OK",
            "PARTIAL",
            "COMPILATION_ERROR",
            "RUNTIME_ERROR",
            "WRONG_ANSWER",
            "WRONG_ANSWER",
            "TIME_LIMIT_EXCEEDED",
            "MEMORY_LIMIT_EXCEEDED",
            "IDLENESS_LIMIT_EXCEEDED",
            "SECURITY_VIOLATED",
            "CRASHED",
            "INPUT_PREPARATION_CRASHED",
            "CHALLENGED",
            "SKIPPED",
            "TESTING",
            "REJECTED",
        ]
        | None
    ) = None
    testset: str
    passedTestCount: int
    timeConsumedMillis: int
    memoryConsumedBytes: int
    points: float | None = None
    synthetic: SubmissionSynthetic = Field(default_factory=SubmissionSynthetic)


class RatingChange(BaseModel):
    contestId: int
    contestName: str
    "Localized."
    handle: str
    "Codeforces user handle."
    rank: int
    """
    Place of the user in the contest.
    This field contains user rank on the moment of rating update.
    If afterwards rank changes (e.g. someone get disqualified), this field will not be update and will contain old rank.
    """
    ratingUpdateTimeSeconds: int
    "Time, when rating for the contest was update, in unix-format."
    oldRating: int
    "User rating before the contest."
    newRating: int
    "User rating after the contest."


class Contest(BaseModel):
    id: int
    name: str
    "Localized."
    type: Literal["CF", "IOI", "ICPC"]
    "Scoring system used for the contest."
    phase: Literal["BEFORE", "CODING", "PENDING_SYSTEM_TEST", "SYSTEM_TEST", "FINISHED"]
    frozen: bool
    "If true, then the ranklist for the contest is frozen and shows only submissions, created before freeze."
    durationSeconds: int
    "Duration of the contest in seconds."
    freezeDurationSeconds: int | None = None
    "The ranklist freeze duration of the contest in seconds if any."
    startTimeSeconds: int | None = None
    "Contest start time in unix format."
    relativeTimeSeconds: int | None = None
    "Number of seconds, passed after the start of the contest. Can be negative."
    preparedBy: str | None = None
    "Handle of the user, how created the contest."
    websiteUrl: str | None = None
    "URL for contest-related website."
    description: str | None = None
    "Localized."
    difficulty: int | None = None
    "From 1 to 5. Larger number means more difficult problems."
    kind: str | None = None
    """
    Localized.
    Human-readable type of the contest from the following categories:
    - Official ICPC Contest
    - Official School Contest
    - Opencup Contest
    - School/University/City/Region Championship
    - Training Camp Contest
    - Official International Personal Contest
    - Training Contest.
    """
    icpcRegion: str | None = None
    "Localized. Name of the Region for official ICPC contests."
    country: str | None = None
    "Localized."
    city: str | None = None
    "Localized."
    season: str | None = None


T = TypeVar("T")


class CodeforcesOk(BaseModel, Generic[T]):
    status: Literal["OK"]
    result: T


class CodeforcesFailed(BaseModel):
    status: Literal["FAILED"]
    comment: str


_last_codeforces_call: float | None = None


class CodeforcesException(Exception):
    status_code: int | Literal["api"]

    def __init__(self, status_code: int | Literal["api"], msg: str):
        self.status_code = status_code
        super().__init__(msg)


def call_any(method: str, params: dict[str, str], model: type[T]) -> T:
    global _last_codeforces_call  # noqa: PLW0603
    now = time.monotonic()
    if _last_codeforces_call is not None and now - _last_codeforces_call < config.codeforces_cooldown:
        to_sleep = _last_codeforces_call + config.codeforces_cooldown - now
        time.sleep(to_sleep)
    _last_codeforces_call = now
    log.info("calling api: %s %s", method, params)
    timestamp = round(time.time())
    rand = "".join(random.choices("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ", k=6))
    params["apiKey"] = config.codeforces_apikey
    params["time"] = str(timestamp)
    param_list = sorted(params.items())
    api_sig_plain = f"{rand}/{method}?{urlencode(param_list)}#{config.codeforces_secret}"
    api_sig = f"{rand}{sha512(api_sig_plain.encode()).hexdigest()}"
    param_list.append(("apiSig", api_sig))
    url = f"https://codeforces.com/api/{method}?{urlencode(param_list)}"
    resp = requests.get(url)
    tries = 1
    while (resp.status_code == 502 or resp.status_code == 504) and tries < config.codeforces_max_retries:
        log.warning("got error %s, retrying in %s seconds...", resp.status_code, config.codeforces_retry_delay)
        time.sleep(config.codeforces_retry_delay)
        resp = requests.get(url)
        tries += 1
    result = None
    try:
        result = TypeAdapter[CodeforcesOk[T] | CodeforcesFailed](CodeforcesOk[model] | CodeforcesFailed).validate_json(
            resp.text
        )
    except ValidationError as e:
        result = e
    if isinstance(result, CodeforcesFailed):
        comment = result.comment
    else:
        comment = "-"
    if resp.status_code < 200 or resp.status_code >= 300:
        log.error("failed response content: %s", resp.text)
        raise CodeforcesException(resp.status_code, f"HTTP error {resp.status_code} {resp.reason or '-'} {comment}")
    match result:
        case CodeforcesOk():
            return result.result
        case ValidationError():
            raise CodeforcesException("api", f"codeforces api validation error: {result}") from result
        case CodeforcesFailed():
            raise CodeforcesException("api", f"codeforces api error: {comment}")


def contest_list(*, gym: bool | None = None, group_code: str | None = None) -> list[Contest]:
    params: dict[str, str] = {}
    if gym is not None:
        params["gym"] = "true" if gym else "false"
    if group_code is not None:
        params["groupCode"] = group_code
    return call_any("contest.list", params, list[Contest])


def contest_status(contest_id: str) -> list[Submission]:
    try:
        return call_any(
            "contest.status",
            {"contestId": contest_id},
            list[Submission],
        )
    except CodeforcesException as e:
        if e.status_code == 404:
            raise CodeforcesException(e.status_code, f"Contest with ID '{contest_id}' not found") from e
        else:
            raise e


def user_status(handle: str) -> list[Submission]:
    try:
        return call_any(
            "user.status",
            {"handle": handle},
            list[Submission],
        )
    except CodeforcesException as e:
        if e.status_code == 404:
            raise CodeforcesException(e.status_code, f"User with handle '{handle}' not found") from e
        else:
            raise e


def user_rating(handle: str) -> list[RatingChange]:
    try:
        return call_any(
            "user.rating",
            {"handle": handle},
            list[RatingChange],
        )
    except CodeforcesException as e:
        if e.status_code == 404:
            raise CodeforcesException(e.status_code, f"User with handle '{handle}' not found") from e
        else:
            raise e
