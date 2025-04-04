import os.path
from datetime import datetime
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore[reportMissingModuleSource]

from app import logic
from app.settings import config

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def compute_results(in_mat: list[list[str]]) -> list[list[str]]:
    if len(in_mat) < 1:
        raise RuntimeError("expected header row")
    # Pack up handles and commands
    handles: list[tuple[int, str]] = []
    commands: list[tuple[int, str]] = []
    for i, row in enumerate(in_mat[1:]):
        if row and row[0]:
            handles.append((i, row[0]))
    for j, cmd in enumerate(in_mat[0][1:]):
        if cmd:
            commands.append((j, cmd))
    # Call the inner compute function to compute the result of handle x command matrix
    out = logic.compute([c for _, c in commands], [h for _, h in handles])
    # Spread the results around the result matrix
    out_mat = [["" for _ in range(len(in_mat[0]) - 1)] for _ in range(len(in_mat) - 1)]
    for (j, _), cmd_out in zip(commands, out):
        for (i, _), outelem in zip(handles, cmd_out.by_handle):
            if isinstance(outelem, str):
                out_mat[i][j] = f"'{outelem}"
            if isinstance(outelem, int):
                out_mat[i][j] = str(outelem)
    return out_mat


def authorize() -> Credentials:
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("./config/token.json"):
        creds = Credentials.from_authorized_user_file("./config/token.json", SCOPES)  # pyright: ignore[reportUnknownMemberType]
    else:
        creds = None
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:  # pyright: ignore[reportUnknownMemberType]
            creds.refresh(Request())  # pyright: ignore[reportUnknownMemberType]
        else:
            flow = InstalledAppFlow.from_client_secrets_file("./config/credentials.json", SCOPES)  # pyright: ignore[reportUnknownMemberType]
            creds = flow.run_local_server(port=0)  # pyright: ignore[reportUnknownMemberType]
        # Save the credentials for the next run
        with open("./config/token.json", "w") as token:
            token.write(creds.to_json())  # pyright: ignore[reportUnknownMemberType]

    return creds


def a1_cell(row: int, col: int) -> str:
    # Format column
    outcol = ""
    col += 1
    while col:
        digit = col % 26
        if digit == 0:
            digit = 26
        outcol += chr(ord("A") + digit - 1)
        col = (col - digit) // 26
    outcol = outcol[::-1]

    # Format row
    outrow = ""
    row += 1
    while row:
        digit = row % 10
        outrow += chr(ord("0") + digit)
        row = row // 10
    outrow = outrow[::-1]

    return f"{outcol}{outrow}"


def a1_range(sheet_name: str, start: tuple[int, int], end: tuple[int, int]) -> str:
    return f"'{sheet_name}'!{a1_cell(start[0], start[1])}:{a1_cell(end[0], end[1])}"


def main():
    creds = authorize()
    service: SheetsResource = build("sheets", "v4", credentials=creds)  # pyright: ignore[reportAssignmentType]

    # Descargar info del sheets
    updtime = datetime.now()
    sheet: SheetsResource.SpreadsheetsResource = service.spreadsheets()
    in_mat = (
        sheet.values()
        .get(
            spreadsheetId=config.spreadsheet_id,
            range=f"'{config.sheet_name}'",
        )
        .execute()
    ).get("values", [])

    # Show "calculating..."
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (0, 0), (0, 0)),
        body={"values": [[f"Updating... ({updtime})"]]},
        valueInputOption="RAW",
    ).execute()

    try:
        # Compute results
        out_mat: list[list[str]] = compute_results(in_mat)
    except Exception as e:
        # Upload error to sheets
        sheet.values().update(
            spreadsheetId=config.spreadsheet_id,
            range=a1_range(config.sheet_name, (0, 0), (0, 0)),
            body={"values": [[f"ERROR ({updtime}): {e}"]]},
            valueInputOption="RAW",
        ).execute()
        raise e

    # Update with results
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (1, 1), (len(out_mat), len(out_mat[0]) if out_mat else 0)),
        body={"values": out_mat},
        valueInputOption="USER_ENTERED",
    ).execute()
    msg = f"Updated at {updtime}"
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (0, 0), (0, 0)),
        body={"values": [[msg]]},
        valueInputOption="RAW",
    ).execute()
    print(msg)


if __name__ == "__main__":
    main()
