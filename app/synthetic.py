from pydantic import BaseModel


class SubmissionSynthetic(BaseModel):
    """
    Mutable info associated to a submission.
    This data is not fetched from codeforces, but rather derived from it.
    """

    points: int | None = None
    points_with_coupon: int | None = None
