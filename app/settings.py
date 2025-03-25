from dataclasses import dataclass
from typing import Any, TypeVar

from dotenv import dotenv_values, load_dotenv


@dataclass
class ConfigVars:
    spreadsheet_id: str
    sheet_name: str


T = TypeVar("T")


def _load_config(model: type[T]) -> T:
    load_dotenv(dotenv_path=".env", override=True)
    env_vars = dotenv_values()

    fields: dict[str, Any] = {}
    errs: list[str] = []
    for field, ty in ConfigVars.__annotations__.items():
        env_name = field.upper()
        val_raw = env_vars.get(env_name, None)
        if val_raw is None:
            if hasattr(ConfigVars, field):
                val_raw = getattr(ConfigVars, field)
            else:
                errs.append(f"Missing variable '{env_name}'")
                continue
        try:
            val = ty(val_raw)
        except Exception as e:
            errs.append(f"Invalid value for variable '{env_name}': {e}")
            continue
        fields[field] = val

    if errs:
        raise RuntimeError(
            f"Errors parsing environment variables:\n{'\n'.join(errs)}\nMaybe complete your `.env` file?"
        )

    return model(**fields)


config: ConfigVars = _load_config(ConfigVars)
