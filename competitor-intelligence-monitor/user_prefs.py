import os
import json
import base64
from datetime import datetime

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv(override=True)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
PREFS_TAB = "User Preferences"
PREFS_HEADERS = [
    "Slack User ID", "Name", "Team",
    "Days", "Categories", "Include Nimble", "Format",
    "Output", "Email", "Last Sent", "Last Updated",
]


def _get_sheet():
    creds_b64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    creds_file = os.getenv("GOOGLE_SHEETS_CREDS_FILE")
    if creds_b64:
        creds = Credentials.from_service_account_info(
            json.loads(base64.b64decode(creds_b64)), scopes=SCOPES)
    elif creds_file:
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    else:
        raise RuntimeError("No Google Sheets credentials configured.")
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.getenv("GOOGLE_SHEET_ID"))


def _ensure_tab(sh) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(PREFS_TAB)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=PREFS_TAB, rows=500, cols=len(PREFS_HEADERS))
        ws.freeze(rows=1)
    # Always rewrite header row, padding with empty strings to clear any stale columns
    ws.update(values=[PREFS_HEADERS + [""] * 20], range_name="A1", value_input_option="RAW")
    return ws


def load_all_prefs() -> dict:
    """Returns {slack_user_id: prefs_dict} for all registered users."""
    try:
        sh = _get_sheet()
        ws = _ensure_tab(sh)
        # Use get_all_values() + manual parse to avoid gspread's duplicate-header error
        # when the sheet has extra empty columns beyond our 11 known headers.
        all_values = ws.get_all_values()
        if not all_values:
            return {}
        header = all_values[0]
        # Build col index from our known headers only; ignore unknown/empty columns
        col = {h: i for i, h in enumerate(header) if h in PREFS_HEADERS}

        def cell(row, name):
            i = col.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        result = {}
        for row in all_values[1:]:
            uid = cell(row, "Slack User ID")
            if not uid:
                continue
            days_raw = cell(row, "Days")
            cats_raw = cell(row, "Categories")
            result[uid] = {
                "name":          cell(row, "Name"),
                "team":          cell(row, "Team"),
                "days":          [d.strip() for d in days_raw.split(",") if d.strip()],
                "categories":    [c.strip() for c in cats_raw.split(",") if c.strip()],
                "include_nimble": cell(row, "Include Nimble") != "No",
                "format":        cell(row, "Format") or "detailed",
                "output":        cell(row, "Output") or "slack",
                "email":         cell(row, "Email"),
                "last_sent":     cell(row, "Last Sent")[:10],  # strip time if present
            }
        return result
    except Exception as e:
        print(f"[Prefs] Load error: {e}")
        return {}


def save_prefs(slack_user_id: str, prefs: dict) -> None:
    sh = _get_sheet()
    ws = _ensure_tab(sh)

    row_data = [
        slack_user_id,
        prefs.get("name", ""),
        prefs.get("team", ""),
        ", ".join(prefs.get("days", [])),
        ", ".join(prefs.get("categories", [])),
        "Yes" if prefs.get("include_nimble", True) else "No",
        prefs.get("format", "detailed"),
        prefs.get("output", "slack"),
        prefs.get("email", ""),
        prefs.get("last_sent", ""),
        datetime.now().strftime("%Y-%m-%d %H:%M"),
    ]

    all_ids = ws.col_values(1)[1:]  # skip header row
    if slack_user_id in all_ids:
        row_num = all_ids.index(slack_user_id) + 2  # 1-indexed + header
        ws.update(values=[row_data], range_name=f"A{row_num}", value_input_option="RAW")
    else:
        ws.append_row(row_data, value_input_option="RAW")
