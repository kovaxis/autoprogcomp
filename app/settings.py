import json
import os
from typing import Any, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel


class Schedule(BaseModel):
    hour: int | None
    minute: int


class ConfigVars(BaseModel):
    codeforces_apikey: str
    codeforces_secret: str
    spreadsheet_id: str
    sheet_name: str = "Codeforces"
    schedule: Schedule = Schedule(hour=0, minute=0)
    codeforces_cooldown: float = 2
    codeforces_retry_delay: float = 10
    codeforces_max_retries: int = 3


T = TypeVar("T", bound=BaseModel)


def try_jsonparse(s: str) -> Any:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


def _load_config(model: type[T]) -> T:
    load_dotenv(dotenv_path="./config/.env", override=True)

    mapped_env_vars = {key.lower(): try_jsonparse(val) for key, val in os.environ.items()}

    return model.model_validate(mapped_env_vars)


config: ConfigVars = _load_config(ConfigVars)
