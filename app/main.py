import os.path
import traceback
from datetime import datetime
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4 import SheetsResource  # pyright: ignore[reportMissingModuleSource]

import logging

from app import logic
from app.settings import config

log = logging.getLogger("autoprogcomp")

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
            match outelem:
                case str():
                    out_mat[i][j] = f"'{outelem}"
                case int():
                    out_mat[i][j] = str(outelem)
                case None:
                    out_mat[i][j] = ""
    return out_mat


def authorize() -> Credentials | service_account.Credentials:
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("./config/serviceaccount.json"):
        log.info("using service account...")
        return service_account.Credentials.from_service_account_file("./config/serviceaccount.json", scopes=SCOPES)  # pyright: ignore[reportUnknownMemberType]
    elif os.path.exists("./config/token.json"):
        creds = Credentials.from_authorized_user_file("./config/token.json", SCOPES)  # pyright: ignore[reportUnknownMemberType]
    else:
        creds = None
    if not creds or not creds.valid:
        if os.path.exists("./config/credentials.json"):
            # If there are no (valid) credentials available, let the user log in.
            if creds and creds.expired and creds.refresh_token:  # pyright: ignore[reportUnknownMemberType]
                creds.refresh(Request())  # pyright: ignore[reportUnknownMemberType]
            else:
                flow = InstalledAppFlow.from_client_secrets_file("./config/credentials.json", SCOPES)  # pyright: ignore[reportUnknownMemberType]
                creds = flow.run_local_server(port=0)  # pyright: ignore[reportUnknownMemberType]
            # Save the credentials for the next run
            with open("./config/token.json", "w") as token:
                token.write(creds.to_json())  # pyright: ignore[reportUnknownMemberType]
        else:
            raise RuntimeError("no `serviceaccount.json` or `credentials.json` google auth file found in `./config`")

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


def run():
    updtime = datetime.now(config.timezone)
    log.info("running autoprogcomp aggregator... (%s)", updtime)

    log.info("authorizing google account...")
    creds = authorize()
    service: SheetsResource = build("sheets", "v4", credentials=creds)  # pyright: ignore[reportAssignmentType]

    # Descargar info del sheets
    log.info("fetching google spreadsheet %s...", config.spreadsheet_id)
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
    log.info("modifying spreadsheet to indicate in-progress status...")
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (0, 0), (0, 0)),
        body={"values": [[f"Updating... ({updtime})"]]},
        valueInputOption="RAW",
    ).execute()

    try:
        # Compute results
        log.info("fetching from codeforces and aggregating data...")
        out_mat: list[list[str]] = compute_results(in_mat)
    except BaseException as e:
        # Upload error to sheets
        msg = f"ERROR ({updtime}): {e}"
        log.info("error result: %s", msg)
        log.info("modifying spreadsheet to indicate error...")
        try:
            sheet.values().update(
                spreadsheetId=config.spreadsheet_id,
                range=a1_range(config.sheet_name, (0, 0), (0, 0)),
                body={"values": [[msg]]},
                valueInputOption="RAW",
            ).execute()
        except BaseException:
            traceback.print_exc()
        raise e

    # Update with results
    log.info("modifying spreadsheet to upload results")
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (1, 1), (len(out_mat), len(out_mat[0]) if out_mat else 0)),
        body={"values": out_mat},
        valueInputOption="USER_ENTERED",
    ).execute()
    log.info("modifying spreadsheet to indicate successful status...")
    msg = f"Updated at {updtime}"
    sheet.values().update(
        spreadsheetId=config.spreadsheet_id,
        range=a1_range(config.sheet_name, (0, 0), (0, 0)),
        body={"values": [[msg]]},
        valueInputOption="RAW",
    ).execute()
    log.info("run result: %s", msg)


def setup_logging():
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())


def main():
    setup_logging()
    run()


if __name__ == "__main__":
    main()
