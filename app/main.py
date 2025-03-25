import os.path
import re
from typing import Any, TypeVar

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

from app.settings import config

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def authorize() -> Credentials:
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)  # pyright: ignore[reportUnknownMemberType]
    else:
        creds = None
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:  # pyright: ignore[reportUnknownMemberType]
            creds.refresh(Request())  # pyright: ignore[reportUnknownMemberType]
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())  # pyright: ignore[reportUnknownMemberType]

    return creds


T = TypeVar("T")


def interpret(model: type[T], mat: list[list[str]]) -> list[T]:
    types: dict[str, Any] = {name: ty for name, ty in model.__annotations__.items()}
    patterns: dict[str, str] = {
        name: getattr(model, name)[0] if isinstance(getattr(model, name), tuple) else getattr(model, name)
        for name in model.__annotations__
    }
    defaults: dict[str, Any] = {
        name: getattr(model, name)[1] for name in model.__annotations__ if isinstance(getattr(model, name), tuple)
    }

    start_row = None
    has_columns: set[str] = set()
    need_columns = set(model.__annotations__) - set(defaults)
    names_to_indices: dict[str, int] = {}
    for row_idx, row in enumerate(mat):
        names_to_indices = {}
        for name in model.__annotations__:
            pat = re.compile(patterns[name], re.IGNORECASE)
            for idx, header in enumerate(row):
                if pat.fullmatch(header):
                    names_to_indices[name] = idx
                    break
        columns = set(names_to_indices.keys())
        if columns >= need_columns:
            start_row = row_idx + 1
            break
        else:
            if len(columns) > len(has_columns):
                has_columns = columns

    if start_row is None:
        missing_columns = need_columns - has_columns
        raise RuntimeError(f"Sheet does not have the required columns: {', '.join(sorted(missing_columns))}")

    out: list[T] = []
    for row_idx, row in enumerate(mat[start_row:]):
        input_dict = {}
        for name, idx in names_to_indices.items():
            if idx >= len(row):
                raise RuntimeError(f"Row {row_idx + 1} is missing field {name}")
            val_raw = row[idx]
            ty = types[name]
            try:
                val = ty(val_raw)
            except Exception as e:
                raise RuntimeError(f"Invalid value for field {name} at row {row_idx + 1}: {e}") from e
            input_dict[name] = val
        out.append(model(**input_dict))
    return out


def main():
    creds = authorize()
    service = build("sheets", "v4", credentials=creds)

    # Descargar info del sheets
    sheet = service.spreadsheets()
    in_values = sheet.values().get(spreadsheetId=config.spreadsheet_id, range=config.range).execute()
    in_mat = in_values.get("values", [])

    # Encontrar fila con headers
    for i, row in enumerate(in_mat):
        col_mapping = recognize_headers(row)
        if col_mapping:
            break
    if not col_mapping:
        raise RuntimeError("No se encontró una fila de headers válida")

    # Leer info del sheets
    handles: list[str] = []
    attendances: list[list[str]] = []
    contests: list[str] = []
    for i in range(len(in_mat)):
        j = 0
        # Leer handle
        if i == 0:
            pass
        else:
            handles.append(in_mat[i][j])
        j += 1
        # Leer asistencia
        if i == 0:
            pass
        else:
            attendances.append(in_mat[i][j : j + config.attendance_columns])
        j += config.attendance_columns

    # Generar info
    out_mat: list[list[str]] = []
    for i in range(len(in_mat)):
        out_row: list[str] = []
        # TODO: Contest semanales
        # TODO: Asistencia
        # TODO: Competencias oficiales
        # TODO: Bonus C++
        # TODO: Bonus Codeforces
        # TODO: Bonus problema explicado
        # TODO: Cupones de atraso
        # TODO: Nota final
        out_mat.append(out_row)

    # Actualizar sheets
    sheet.values().update(spreadsheetId=config.spreadsheet_id, range=config.range, body={"values": out_mat})


if __name__ == "__main__":
    main()
