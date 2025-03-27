from typing import TypeVar

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel


class ConfigVars(BaseModel):
    codeforces_apikey: str
    codeforces_secret: str
    spreadsheet_id: str
    sheet_name: str


T = TypeVar("T", bound=BaseModel)


def _load_config(model: type[T]) -> T:
    load_dotenv(dotenv_path=".env", override=True)
    env_vars = dotenv_values()

    mapped_env_vars = {key.lower(): val for key, val in env_vars.items()}

    return model.model_validate(mapped_env_vars)


config: ConfigVars = _load_config(ConfigVars)
