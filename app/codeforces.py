import random
import time
from hashlib import sha512
from typing import Generic, Literal, TypeVar
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, Field, TypeAdapter

from app.settings import config
from app.synthetic import SubmissionSynthetic


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


T = TypeVar("T")


class CodeforcesOk(BaseModel, Generic[T]):
    status: Literal["OK"]
    result: T


class CodeforcesFailed(BaseModel):
    status: Literal["FAILED"]
    comment: str


_last_codeforces_call: float | None = None

API_COOLDOWN: float = 1


def call_any(method: str, params: dict[str, str], model: type[T]) -> T:
    global _last_codeforces_call  # noqa: PLW0603
    now = time.monotonic()
    if _last_codeforces_call is not None and now - _last_codeforces_call < API_COOLDOWN:
        to_sleep = _last_codeforces_call + API_COOLDOWN - now
        time.sleep(to_sleep)
    _last_codeforces_call = now
    print(f"calling codeforces api: {method} {params}")
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
    result = TypeAdapter[CodeforcesOk[T] | CodeforcesFailed](CodeforcesOk[model] | CodeforcesFailed).validate_json(
        resp.text
    )
    if isinstance(result, CodeforcesFailed):
        raise RuntimeError(f"codeforces api error: {result.comment}")
    resp.raise_for_status()
    return result.result


def contest_status(contest_id: str) -> list[Submission]:
    return call_any(
        "contest.status",
        {"contestId": contest_id},
        list[Submission],
    )


def user_status(handle: str) -> list[Submission]:
    return call_any(
        "user.status",
        {"handle": handle},
        list[Submission],
    )


def user_rating(handle: str) -> list[RatingChange]:
    return call_any(
        "user.rating",
        {"handle": handle},
        list[RatingChange],
    )
