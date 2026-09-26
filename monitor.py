
import os
import re
import json
import time
import imaplib
import email
import smtplib
import html
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

IST = ZoneInfo("Asia/Kolkata")
# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

ERP_USERNAME = os.getenv("ERP_USERNAME")
ERP_PASSWORD = os.getenv("ERP_PASSWORD")

SECURITY_Q1 = os.getenv("SECURITY_Q1")
SECURITY_A1 = os.getenv("SECURITY_A1")

SECURITY_Q2 = os.getenv("SECURITY_Q2")
SECURITY_A2 = os.getenv("SECURITY_A2")

SECURITY_Q3 = os.getenv("SECURITY_Q3")
SECURITY_A3 = os.getenv("SECURITY_A3")

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

MAIL_TO = os.getenv(
    "MAIL_TO",
    GMAIL_ADDRESS
)

NOTICE_MAIL_SUBJECT = os.getenv(
    "NOTICE_MAIL_SUBJECT",
    "IIT KGP CDC Notice Board Update"
)

PLACEMENT_MAIL_SUBJECT = os.getenv(
    "PLACEMENT_MAIL_SUBJECT",
    "IIT KGP Placement/Internship Board Update"
)

CHECK_INTERVAL_SECONDS = 30 * 60

OTP_WAIT_SECONDS = 60
OTP_MAX_WAIT_SECONDS = 120
OTP_POLL_INTERVAL_SECONDS = 5

# Separate state files.
NOTICE_STATE_FILE = "seen_notices.json"
PLACEMENT_STATE_FILE = "seen_placements.json"


# ============================================================
# ERP URLS
# ============================================================

BASE_URL = "https://erp.iitkgp.ac.in"

ERP_ENTRY_URL = (
    "https://erp.iitkgp.ac.in/IIT_ERP3/"
)

LOGIN_URL = (
    "https://erp.iitkgp.ac.in/SSOAdministration/login.htm"
)

SECURITY_QUESTION_URL = (
    "https://erp.iitkgp.ac.in/SSOAdministration/"
    "getSecurityQues.htm"
)

OTP_URL = (
    "https://erp.iitkgp.ac.in/SSOAdministration/"
    "getEmilOTP.htm"
)

AUTH_URL = (
    "https://erp.iitkgp.ac.in/SSOAdministration/"
    "auth.htm"
)

CLEAR_ALL_SESSIONS_URL = (
    "https://erp.iitkgp.ac.in/SSOAdministration/"
    "clearAllSessions.htm"
)

ERP_HOME_URL = (
    "https://erp.iitkgp.ac.in/IIT_ERP3/home.htm"
)


# ============================================================
# CDC NOTICE BOARD
# ============================================================

NOTICE_PAGE_URL = (
    "https://erp.iitkgp.ac.in/"
    "TrainingPlacementSSO/Notice.jsp"
)

NOTICE_DATA_URL = (
    "https://erp.iitkgp.ac.in/"
    "TrainingPlacementSSO/ERPMonitoring.htm"
)


# ============================================================
# PLACEMENT / INTERNSHIP BOARD
# ============================================================

PLACEMENT_PAGE_URL = (
    "https://erp.iitkgp.ac.in/"
    "TrainingPlacementSSO/TPStudent.jsp"
)

PLACEMENT_DATA_URL = (
    "https://erp.iitkgp.ac.in/"
    "TrainingPlacementSSO/ERPMonitoring.htm"
)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    )
})


# ============================================================
# PERSISTENT DASHBOARD STATE
# ============================================================

DASHBOARD_STATE_FILE = "dashboard_data.json"

DEFAULT_DASHBOARD_DATA = {
    "erp_status": "Starting",
    "last_check": None,
    "next_check": None,
    "notice_count": 0,
    "placement_count": 0,
    "notices": [],
    "placements": [],
    "last_error": None
}


def load_dashboard_data():

    if not os.path.exists(DASHBOARD_STATE_FILE):
        return json.loads(json.dumps(DEFAULT_DASHBOARD_DATA))

    try:
        with open(
            DASHBOARD_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            state = json.load(file)

        if not isinstance(state, dict):
            raise ValueError("Dashboard state must be a JSON object.")

        data = json.loads(json.dumps(DEFAULT_DASHBOARD_DATA))
        data.update(state)
        return data

    except Exception as error:
        print(
            "Warning: could not read dashboard_data.json:",
            str(error)
        )
        return json.loads(json.dumps(DEFAULT_DASHBOARD_DATA))


dashboard_data = load_dashboard_data()


def update_dashboard(**values):
    dashboard_data.update(values)


def get_dashboard_data():
    return json.loads(json.dumps(dashboard_data))


def save_dashboard_data():

    temp_file = DASHBOARD_STATE_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            dashboard_data,
            file,
            indent=2,
            ensure_ascii=False
        )
        file.write("\n")

    os.replace(
        temp_file,
        DASHBOARD_STATE_FILE
    )


def current_time_string():

    return datetime.now(IST).strftime(
        "%d %b %Y, %I:%M:%S %p"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def validate_environment():

    required = {

        "ERP_USERNAME":
            ERP_USERNAME,

        "ERP_PASSWORD":
            ERP_PASSWORD,

        "SECURITY_Q1":
            SECURITY_Q1,

        "SECURITY_A1":
            SECURITY_A1,

        "SECURITY_Q2":
            SECURITY_Q2,

        "SECURITY_A2":
            SECURITY_A2,

        "SECURITY_Q3":
            SECURITY_Q3,

        "SECURITY_A3":
            SECURITY_A3,

        "GMAIL_ADDRESS":
            GMAIL_ADDRESS,

        "GMAIL_APP_PASSWORD":
            GMAIL_APP_PASSWORD,

        "MAIL_TO":
            MAIL_TO,
    }


    missing = [
        key
        for key, value in required.items()
        if not value
    ]


    if missing:

        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


def question_answer_map():

    return {

        SECURITY_Q1.strip():
            SECURITY_A1,

        SECURITY_Q2.strip():
            SECURITY_A2,

        SECURITY_Q3.strip():
            SECURITY_A3,
    }


def clean_html(text):

    if not text:
        return ""

    return BeautifulSoup(
        text,
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )


def get_numeric_id(value):

    try:

        return int(
            str(value)
        )

    except (
        ValueError,
        TypeError
    ):

        return -1


# ============================================================
# ERP ENTRY
# ============================================================

def open_erp():

    print()
    print(
        "Opening IIT KGP ERP..."
    )


    response = session.get(
        ERP_ENTRY_URL,
        allow_redirects=True,
        timeout=30
    )


    print(
        "ERP entry status:",
        response.status_code
    )


    session_token = None

    requested_url = (
        ERP_ENTRY_URL
    )


    urls_to_check = [
        response.url
    ]


    for history_response in (
        response.history
    ):

        urls_to_check.append(
            history_response.url
        )

        location = (
            history_response.headers.get(
                "Location",
                ""
            )
        )

        if location:

            urls_to_check.append(
                location
            )


    for url in urls_to_check:

        if not url:
            continue

        try:

            parsed = urlparse(
                url
            )

            query = parse_qs(
                parsed.query
            )


            if query.get(
                "sessionToken"
            ):

                session_token = (
                    query[
                        "sessionToken"
                    ][0]
                )


            if query.get(
                "requestedUrl"
            ):

                requested_url = (
                    query[
                        "requestedUrl"
                    ][0]
                )

        except Exception:

            pass


    if not session_token:

        raise RuntimeError(
            "Could not obtain ERP login session token."
        )


    print(
        "Login session token obtained."
    )


    return (
        session_token,
        requested_url
    )


# ============================================================
# SECURITY QUESTION
# ============================================================

def get_security_question():

    print(
        "Fetching security question..."
    )


    response = session.post(
        SECURITY_QUESTION_URL,

        data={
            "user_id":
                ERP_USERNAME
        },

        timeout=30
    )


    response.raise_for_status()


    try:

        data = response.json()

        question = (
            data.get(
                "securityQuestion"
            )
            or
            data.get(
                "question"
            )
            or
            data.get(
                "msg"
            )
        )

    except ValueError:

        question = (
            response.text.strip()
        )


    if not question:

        raise RuntimeError(
            "Could not obtain ERP security question."
        )


    print(
        "Security question received."
    )


    answers = (
        question_answer_map()
    )


    answer = answers.get(
        question.strip()
    )


    if not answer:

        raise RuntimeError(
            "No answer configured for this "
            "security question."
        )


    print(
        "Matching security answer found."
    )


    return answer


# ============================================================
# GMAIL / OTP
# ============================================================

def connect_gmail():

    print(
        "Connecting to Gmail..."
    )


    mail = imaplib.IMAP4_SSL(
        "imap.gmail.com",
        993
    )


    mail.login(
        GMAIL_ADDRESS,
        GMAIL_APP_PASSWORD
    )


    mail.select(
        "INBOX"
    )


    print(
        "Gmail connection successful."
    )


    return mail


def get_gmail_message_ids(
    mail
):

    status, data = mail.search(
        None,
        "ALL"
    )


    if status != "OK":
        return set()


    return {
        item.decode(
            errors="ignore"
        )
        for item in data[0].split()
    }


def extract_otp(text):

    matches = re.findall(
        r"\b\d{6}\b",
        text
    )


    if not matches:
        return None


    return matches[0]


def looks_like_erp_email(
    msg
):

    sender = (
        msg.get(
            "From",
            ""
        ).lower()
    )

    subject = (
        msg.get(
            "Subject",
            ""
        ).lower()
    )


    return (
        "erpkgp@adm.iitkgp.ac.in"
        in sender
        or
        "otp"
        in subject
    )


def extract_email_body(
    msg
):

    parts = []


    if msg.is_multipart():

        for part in msg.walk():

            content_type = (
                part.get_content_type()
            )


            if content_type not in (
                "text/plain",
                "text/html"
            ):

                continue


            try:

                payload = (
                    part.get_payload(
                        decode=True
                    )
                )


                if payload:

                    parts.append(
                        payload.decode(
                            errors="ignore"
                        )
                    )

            except Exception:

                pass

    else:

        try:

            payload = (
                msg.get_payload(
                    decode=True
                )
            )


            if payload:

                parts.append(
                    payload.decode(
                        errors="ignore"
                    )
                )

        except Exception:

            pass


    return "\n".join(
        parts
    )


def wait_for_otp(
    mail,
    existing_ids,
    max_wait=OTP_MAX_WAIT_SECONDS
):

    print()
    print(
        "Checking Gmail for ERP OTP..."
    )


    start_time = time.time()


    while (
        time.time() - start_time
        < max_wait
    ):

        mail.select(
            "INBOX"
        )


        status, data = (
            mail.search(
                None,
                "ALL"
            )
        )


        if status != "OK":

            time.sleep(
                OTP_POLL_INTERVAL_SECONDS
            )

            continue


        current_ids = [

            item.decode(
                errors="ignore"
            )

            for item in data[0].split()
        ]


        new_ids = [

            item

            for item in current_ids

            if item not in existing_ids
        ]


        for message_id in reversed(
            new_ids
        ):

            status, message_data = (
                mail.fetch(
                    message_id,
                    "(RFC822)"
                )
            )


            if status != "OK":
                continue


            raw_email = (
                message_data[0][1]
            )


            msg = (
                email.message_from_bytes(
                    raw_email
                )
            )


            if not looks_like_erp_email(
                msg
            ):

                continue


            print(
                "ERP OTP email detected."
            )


            body = (
                extract_email_body(
                    msg
                )
            )


            otp = extract_otp(
                body
            )


            if otp:

                print(
                    "OTP detected successfully."
                )

                return otp


        time.sleep(
            OTP_POLL_INTERVAL_SECONDS
        )


    return None


def request_otp(
    session_token,
    requested_url,
    answer
):

    print()
    print(
        "Recording existing Gmail messages..."
    )


    mail = connect_gmail()


    existing_ids = (
        get_gmail_message_ids(
            mail
        )
    )


    print(
        "Existing Gmail messages recorded:",
        len(existing_ids)
    )


    print()
    print(
        "Requesting ERP OTP..."
    )


    response = session.post(

        OTP_URL,

        data={

            "user_id":
                ERP_USERNAME,

            "password":
                ERP_PASSWORD,

            "answer":
                answer,

            "typeee":
                "SI",

            "email_otp":
                "",

            "sessionToken":
                session_token,

            "requestedUrl":
                requested_url,
        },

        timeout=30
    )


    print(
        "OTP request status:",
        response.status_code
    )


    print(
        f"Waiting {OTP_WAIT_SECONDS} seconds "
        "for the ERP email..."
    )


    time.sleep(
        OTP_WAIT_SECONDS
    )


    otp = wait_for_otp(
        mail,
        existing_ids
    )


    try:

        mail.logout()

    except Exception:

        pass


    if not otp:

        raise RuntimeError(
            "Could not find the new ERP OTP email."
        )


    return otp


# ============================================================
# ERP AUTHENTICATION
# ============================================================

def authenticate_with_otp(
    session_token,
    requested_url,
    answer,
    otp
):

    print()
    print(
        "Authenticating with IIT KGP ERP..."
    )


    response = session.post(

        AUTH_URL,

        data={

            "user_id":
                ERP_USERNAME,

            "password":
                ERP_PASSWORD,

            "answer":
                answer,

            "typeee":
                "SI",

            "email_otp":
                otp,

            "sessionToken":
                session_token,

            "requestedUrl":
                requested_url,
        },

        headers={

            "Origin":
                BASE_URL,

            "Referer":
                LOGIN_URL,
        },

        timeout=30,

        allow_redirects=True
    )


    print(
        "ERP authentication status:",
        response.status_code
    )


    return response


def is_previous_session_page(
    response
):

    text = BeautifulSoup(
        response.text,
        "html.parser"
    ).get_text(
        " ",
        strip=True
    ).lower()


    return (
        "your previous session is still active"
        in text
    )


# ============================================================
# CLEAR PREVIOUS ERP SESSIONS
# ============================================================

def clear_all_sessions():

    print()
    print(
        "Previous ERP session is active."
    )


    print(
        "Clearing previous ERP sessions..."
    )


    response = session.post(

        CLEAR_ALL_SESSIONS_URL,

        data={
            "user_code":
                ERP_USERNAME
        },

        headers={

            "Accept":
                "text/plain, */*; q=0.01",

            "Content-Type":
                "application/x-www-form-urlencoded; "
                "charset=UTF-8",

            "Origin":
                BASE_URL,

            "Referer":
                AUTH_URL,

            "X-Requested-With":
                "XMLHttpRequest",
        },

        timeout=30,

        allow_redirects=True
    )


    print(
        "Clear-session request status:",
        response.status_code
    )


    if response.status_code != 200:

        raise RuntimeError(
            "Could not clear previous ERP sessions."
        )


    print(
        "Previous ERP sessions cleared."
    )


# ============================================================
# VERIFY ERP SESSION
# ============================================================

def verify_erp_session():

    print(
        "Verifying authenticated ERP session..."
    )


    response = session.get(

        ERP_HOME_URL,

        timeout=30,

        allow_redirects=True
    )


    print(
        "ERP verification status:",
        response.status_code
    )


    final_url = (
        response.url.lower()
    )


    if (
        "/iit_erp3/home.htm"
        not in final_url
        or
        "login"
        in final_url
    ):

        return False


    return True


def authenticate_erp():

    update_dashboard(
        erp_status="Authenticating",
        last_error=None
    )


    for attempt in range(
        1,
        3
    ):

        print()
        print(
            "=" * 60
        )

        print(
            f"ERP LOGIN ATTEMPT {attempt}/2"
        )

        print(
            "=" * 60
        )


        session_token, requested_url = (
            open_erp()
        )


        answer = (
            get_security_question()
        )


        otp = request_otp(

            session_token,
            requested_url,
            answer
        )


        response = (
            authenticate_with_otp(

                session_token,
                requested_url,
                answer,
                otp
            )
        )


        if is_previous_session_page(
            response
        ):

            if attempt == 1:

                clear_all_sessions()

                session.cookies.clear()


                print()
                print(
                    "Starting fresh ERP authentication..."
                )


                continue


            raise RuntimeError(
                "ERP still reports a previous active "
                "session after clearing all sessions."
            )


        if verify_erp_session():

            print()
            print(
                "ERP authentication successful."
            )


            update_dashboard(
                erp_status="Connected",
                last_error=None
            )


            return True


        if attempt == 1:

            print(
                "Authentication verification failed."
            )

            print(
                "Retrying authentication..."
            )


    raise RuntimeError(
        "ERP authentication failed."
    )


# ============================================================
# NOTICE STATE
# ============================================================

def load_notice_state():

    if not os.path.exists(
        NOTICE_STATE_FILE
    ):

        return {
            "last_notified_id":
                None
        }


    try:

        with open(
            NOTICE_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            state = json.load(
                file
            )


        if not isinstance(
            state,
            dict
        ):

            raise ValueError


        return {
            "last_notified_id":
                state.get(
                    "last_notified_id"
                )
        }


    except Exception:

        print(
            "Warning: could not read "
            "seen_notices.json."
        )


        return {
            "last_notified_id":
                None
        }


def save_notice_state(
    state
):

    temp_file = (
        NOTICE_STATE_FILE
        + ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            indent=2
        )


    os.replace(
        temp_file,
        NOTICE_STATE_FILE
    )


# ============================================================
# PLACEMENT STATE
# ============================================================

def load_placement_state():

    if not os.path.exists(
        PLACEMENT_STATE_FILE
    ):

        return {
            "initialized":
                False,

            "seen_ids":
                []
        }


    try:

        with open(
            PLACEMENT_STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            state = json.load(
                file
            )


        if not isinstance(
            state,
            dict
        ):

            raise ValueError


        return {

            "initialized":
                bool(
                    state.get(
                        "initialized",
                        False
                    )
                ),

            "seen_ids":
                list(
                    state.get(
                        "seen_ids",
                        []
                    )
                )
        }


    except Exception:

        print(
            "Warning: could not read "
            "seen_placements.json."
        )


        return {

            "initialized":
                False,

            "seen_ids":
                []
        }


def save_placement_state(
    state
):

    temp_file = (
        PLACEMENT_STATE_FILE
        + ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            indent=2
        )


    os.replace(
        temp_file,
        PLACEMENT_STATE_FILE
    )


# ============================================================
# CDC NOTICE BOARD
# ============================================================

def fetch_notice_board():

    print()
    print(
        "Opening CDC Notice Board..."
    )


    page_response = session.get(

        NOTICE_PAGE_URL,

        timeout=30
    )


    print(
        "Notice page status:",
        page_response.status_code
    )


    if (
        "login.htm"
        in page_response.url.lower()
        or
        "ssoadministration"
        in page_response.url.lower()
    ):

        raise RuntimeError(
            "ERP session appears to have expired."
        )


    params = {

        "action":
            "fetchData",

        "jqqueryid":
            "54",

        "_search":
            "false",

        "nd":
            str(
                int(
                    time.time()
                    * 1000
                )
            ),

        "rows":
            "100",

        "page":
            "1",

        "sidx":
            "",

        "sord":
            "asc",

        "totalrows":
            "50",
    }


    response = session.get(

        NOTICE_DATA_URL,

        params=params,

        headers={

            "Accept":
                "application/xml, text/xml, "
                "*/*; q=0.01",

            "X-Requested-With":
                "XMLHttpRequest",

            "Referer":
                NOTICE_PAGE_URL,
        },

        timeout=30
    )


    print(
        "Notice data status:",
        response.status_code
    )


    if response.status_code != 200:

        raise RuntimeError(
            "CDC Notice Board request failed."
        )


    if (
        "login.htm"
        in response.url.lower()
        or
        "ssoadministration"
        in response.url.lower()
    ):

        raise RuntimeError(
            "ERP session appears to have expired."
        )


    try:

        root = ET.fromstring(
            response.text
        )

    except ET.ParseError as error:

        raise RuntimeError(
            "Could not parse CDC Notice Board XML."
        ) from error


    notices = []


    for row in root.findall(
        "row"
    ):

        row_id = row.attrib.get(
            "id",
            ""
        )


        cells = row.findall(
            "cell"
        )


        values = [

            clean_html(
                cell.text or ""
            )

            for cell in cells
        ]


        if not values:
            continue


        notice = {

            "id":
                str(
                    values[0]
                    if len(values) > 0
                    else row_id
                ),

            "type":
                (
                    values[1]
                    if len(values) > 1
                    else ""
                ),

            "subject":
                (
                    values[2]
                    if len(values) > 2
                    else ""
                ),

            "company":
                (
                    values[3]
                    if len(values) > 3
                    else ""
                ),

            "notice":
                (
                    values[4]
                    if len(values) > 4
                    else ""
                ),

            "notice_by":
                (
                    values[5]
                    if len(values) > 5
                    else ""
                ),

            "notice_time":
                (
                    values[6]
                    if len(values) > 6
                    else ""
                ),
        }


        if notice["id"]:

            notices.append(
                notice
            )


    print(
        "CDC notices fetched:",
        len(notices)
    )


    return notices


def get_new_notices(
    notices,
    state
):

    if not notices:

        return []


    last_id = (
        state.get(
            "last_notified_id"
        )
    )


    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if last_id is None:

        sorted_notices = sorted(

            notices,

            key=lambda item:
                get_numeric_id(
                    item["id"]
                ),

            reverse=True
        )


        newest = (
            sorted_notices[:3]
        )


        print(
            "CDC Notice Board first run."
        )


        print(
            "Newest notices selected for email:",
            len(newest)
        )


        return newest


    # --------------------------------------------------------
    # SUBSEQUENT RUNS
    # --------------------------------------------------------

    try:

        last_number = int(
            last_id
        )

    except (
        ValueError,
        TypeError
    ):

        last_number = -1


    new_notices = [

        notice

        for notice in notices

        if get_numeric_id(
            notice["id"]
        ) > last_number
    ]


    new_notices.sort(

        key=lambda item:
            get_numeric_id(
                item["id"]
            )
    )


    return new_notices


# ============================================================
# PLACEMENT / INTERNSHIP BOARD
# ============================================================

def open_placement_board():

    print()
    print(
        "Opening Placement/Internship Board..."
    )


    sso_token = None


    for cookie in session.cookies:

        if cookie.name == "ssoToken":

            sso_token = cookie.value

            break


    if not sso_token:

        raise RuntimeError(
            "Authenticated ERP ssoToken cookie not found."
        )


    response = session.post(

        PLACEMENT_PAGE_URL,

        data={

            "ssoToken":
                sso_token,

            "module_id":
                "26",

            "menu_id":
                "11",
        },

        headers={

            "Accept":
                (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),

            "Content-Type":
                "application/x-www-form-urlencoded",

            "Referer":
                (
                    "https://erp.iitkgp.ac.in/"
                    "IIT_ERP3/showmenu.htm"
                ),
        },

        timeout=30,

        allow_redirects=True
    )


    print(
        "Placement page status:",
        response.status_code
    )


    if (
        "login.htm"
        in response.url.lower()
        or
        "ssoadministration"
        in response.url.lower()
    ):

        raise RuntimeError(
            "ERP session appears to have expired."
        )


    if response.status_code != 200:

        raise RuntimeError(
            "Could not open Placement/Internship Board."
        )


    return response


def fetch_placement_board():

    open_placement_board()


    params = {

        "action":
            "fetchData",

        "jqqueryid":
            "37",

        "_search":
            "false",

        "nd":
            str(
                int(
                    time.time()
                    * 1000
                )
            ),

        "rows":
            "100",

        "page":
            "1",

        "sidx":
            "",

        "sord":
            "asc",

        "totalrows":
            "50",
    }


    response = session.get(

        PLACEMENT_DATA_URL,

        params=params,

        headers={

            "Accept":
                "application/xml, text/xml, "
                "*/*; q=0.01",

            "X-Requested-With":
                "XMLHttpRequest",

            "Referer":
                PLACEMENT_PAGE_URL,
        },

        timeout=30
    )


    print(
        "Placement data status:",
        response.status_code
    )


    if response.status_code != 200:

        raise RuntimeError(
            "Placement/Internship Board request failed."
        )


    if (
        "login.htm"
        in response.url.lower()
        or
        "ssoadministration"
        in response.url.lower()
    ):

        raise RuntimeError(
            "ERP session appears to have expired."
        )


    try:

        root = ET.fromstring(
            response.text
        )

    except ET.ParseError as error:

        raise RuntimeError(
            "Could not parse Placement/Internship "
            "Board XML."
        ) from error


    placements = []


    for row in root.findall(
        "row"
    ):

        row_id = row.attrib.get(
            "id",
            ""
        )


        cells = row.findall(
            "cell"
        )


        values = [

            clean_html(
                cell.text or ""
            )

            for cell in cells
        ]


        if not values:

            continue


        placement = {

            "id":
                str(
                    row_id
                ),

            "company":
                (
                    values[0]
                    if len(values) > 0
                    else ""
                ),

            "additional_details":
                (
                    values[1]
                    if len(values) > 1
                    else ""
                ),

            "ppt":
                (
                    values[2]
                    if len(values) > 2
                    else ""
                ),

            "designation":
                (
                    values[3]
                    if len(values) > 3
                    else ""
                ),

            "description":
                (
                    values[4]
                    if len(values) > 4
                    else ""
                ),

            "ctc":
                (
                    values[5]
                    if len(values) > 5
                    else ""
                ),

            "currency":
                (
                    values[6]
                    if len(values) > 6
                    else ""
                ),

            "additional_details_2":
                (
                    values[7]
                    if len(values) > 7
                    else ""
                ),

            "application_status":
                (
                    values[8]
                    if len(values) > 8
                    else ""
                ),

            "resume_upload_start":
                (
                    values[9]
                    if len(values) > 9
                    else ""
                ),

            "resume_upload_end":
                (
                    values[10]
                    if len(values) > 10
                    else ""
                ),

            "interview_selection":
                (
                    values[11]
                    if len(values) > 11
                    else ""
                ),

            "contract":
                (
                    values[12]
                    if len(values) > 12
                    else ""
                ),
        }


        # ----------------------------------------------------
        # Fallback ID if ERP row does not provide one.
        # ----------------------------------------------------

        if not placement["id"]:

            fallback = "|".join([

                placement["company"],

                placement["designation"],

                placement["description"],

                placement["ctc"],

                placement["resume_upload_start"],

                placement["resume_upload_end"],

                placement["interview_selection"],
            ])


            placement["id"] = fallback


        placements.append(
            placement
        )


    print(
        "Placement/Internship entries fetched:",
        len(placements)
    )


    return placements


def get_new_placements(
    placements,
    state
):

    initialized = (
        state.get(
            "initialized",
            False
        )
    )


    seen_ids = {

        str(value)

        for value in state.get(
            "seen_ids",
            []
        )
    }


    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not initialized:

        print(
            "Placement Board first run."
        )


        # Email only newest/first 3.
        newest = placements[:3]


        print(
            "Placement entries selected for email:",
            len(newest)
        )


        return newest


    # --------------------------------------------------------
    # SUBSEQUENT RUNS
    # --------------------------------------------------------

    new_placements = [

        placement

        for placement in placements

        if str(
            placement["id"]
        ) not in seen_ids
    ]


    return new_placements


# ============================================================
# EMAIL
# ============================================================

def send_email(
    subject,
    html_body,
    plain_body
):

    print()
    print(
        "Sending email..."
    )


    message = MIMEMultipart(
        "alternative"
    )


    message["From"] = (
        GMAIL_ADDRESS
    )

    message["To"] = (
        MAIL_TO
    )

    message["Subject"] = (
        subject
    )


    message.attach(
        MIMEText(
            plain_body,
            "plain",
            "utf-8"
        )
    )


    message.attach(
        MIMEText(
            html_body,
            "html",
            "utf-8"
        )
    )


    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465,
        timeout=30
    ) as smtp:

        smtp.login(
            GMAIL_ADDRESS,
            GMAIL_APP_PASSWORD
        )


        smtp.sendmail(

            GMAIL_ADDRESS,

            [MAIL_TO],

            message.as_string()
        )


    print(
        "Email sent successfully."
    )


# ============================================================
# CDC NOTICE EMAIL
# ============================================================

def send_notice_email(
    notices
):

    if not notices:
        return


    html_parts = [

        "<html>",

        "<body>",

        "<h2>"
        "IIT KGP CDC Notice Board Update"
        "</h2>",
    ]


    plain_parts = [

        "IIT KGP CDC Notice Board Update",

        ""
    ]


    for notice in notices:

        html_parts.append(
            "<hr>"
        )


        html_parts.append(

            "<h3>"
            + html.escape(
                notice["subject"]
            )
            + "</h3>"
        )


        html_parts.append(

            "<p><b>Notice ID:</b> "

            + html.escape(
                notice["id"]
            )

            + "</p>"
        )


        html_parts.append(

            "<p><b>Type:</b> "

            + html.escape(
                notice["type"]
            )

            + "</p>"
        )


        html_parts.append(

            "<p><b>Company:</b> "

            + html.escape(
                notice["company"]
            )

            + "</p>"
        )


        html_parts.append(

            "<p><b>Notice Time:</b> "

            + html.escape(
                notice["notice_time"]
            )

            + "</p>"
        )


        html_parts.append(

            "<p><b>Notice:</b><br>"

            + html.escape(
                notice["notice"]
            ).replace(
                "\n",
                "<br>"
            )

            + "</p>"
        )


        plain_parts.extend([

            "----------------------------------------",

            f"Notice ID: {notice['id']}",

            f"Type: {notice['type']}",

            f"Subject: {notice['subject']}",

            f"Company: {notice['company']}",

            f"Notice Time: {notice['notice_time']}",

            f"Notice: {notice['notice']}",

            ""
        ])


    html_parts.extend([

        "</body>",

        "</html>"
    ])


    send_email(

        NOTICE_MAIL_SUBJECT,

        "".join(
            html_parts
        ),

        "\n".join(
            plain_parts
        )
    )


# ============================================================
# PLACEMENT EMAIL
# ============================================================

def send_placement_email(
    placements
):

    if not placements:
        return


    html_parts = [

        "<html>",

        "<body>",

        "<h2>"
        "IIT KGP Placement/Internship Board Update"
        "</h2>",
    ]


    plain_parts = [

        "IIT KGP Placement/Internship Board Update",

        ""
    ]


    for placement in placements:

        html_parts.append(
            "<hr>"
        )


        html_parts.append(

            "<h3>"

            + html.escape(
                placement["company"]
            )

            + "</h3>"
        )


        if placement[
            "designation"
        ]:

            html_parts.append(

                "<p><b>Role:</b> "

                + html.escape(
                    placement[
                        "designation"
                    ]
                )

                + "</p>"
            )


        if placement["ctc"]:

            html_parts.append(

                "<p><b>CTC:</b> "

                + html.escape(
                    placement["ctc"]
                )

                + " "

                + html.escape(
                    placement["currency"]
                )

                + "</p>"
            )


        if placement[
            "description"
        ]:

            html_parts.append(

                "<p><b>Description:</b><br>"

                + html.escape(
                    placement[
                        "description"
                    ]
                ).replace(
                    "\n",
                    "<br>"
                )

                + "</p>"
            )


        if placement[
            "additional_details"
        ]:

            html_parts.append(

                "<p><b>Additional Details:</b> "

                + html.escape(
                    placement[
                        "additional_details"
                    ]
                )

                + "</p>"
            )


        if placement[
            "application_status"
        ]:

            html_parts.append(

                "<p><b>Application Status:</b> "

                + html.escape(
                    placement[
                        "application_status"
                    ]
                )

                + "</p>"
            )


        if placement[
            "resume_upload_start"
        ]:

            html_parts.append(

                "<p><b>Resume Upload Start:</b> "

                + html.escape(
                    placement[
                        "resume_upload_start"
                    ]
                )

                + "</p>"
            )


        if placement[
            "resume_upload_end"
        ]:

            html_parts.append(

                "<p><b>Resume Upload End:</b> "

                + html.escape(
                    placement[
                        "resume_upload_end"
                    ]
                )

                + "</p>"
            )


        if placement[
            "interview_selection"
        ]:

            html_parts.append(

                "<p><b>Interview/Selection:</b> "

                + html.escape(
                    placement[
                        "interview_selection"
                    ]
                )

                + "</p>"
            )


        if placement[
            "contract"
        ]:

            html_parts.append(

                "<p><b>Contract:</b> "

                + html.escape(
                    placement[
                        "contract"
                    ]
                )

                + "</p>"
            )


        plain_parts.extend([

            "----------------------------------------",

            f"Placement ID: {placement['id']}",

            f"Company: {placement['company']}",

            f"Role: {placement['designation']}",

            (
                f"CTC: {placement['ctc']} "
                f"{placement['currency']}"
            ),

            (
                "Description: "
                f"{placement['description']}"
            ),

            (
                "Additional Details: "
                f"{placement['additional_details']}"
            ),

            (
                "Application Status: "
                f"{placement['application_status']}"
            ),

            (
                "Resume Upload Start: "
                f"{placement['resume_upload_start']}"
            ),

            (
                "Resume Upload End: "
                f"{placement['resume_upload_end']}"
            ),

            (
                "Interview/Selection: "
                f"{placement['interview_selection']}"
            ),

            (
                "Contract: "
                f"{placement['contract']}"
            ),

            ""
        ])


    html_parts.extend([

        "</body>",

        "</html>"
    ])


    send_email(

        PLACEMENT_MAIL_SUBJECT,

        "".join(
            html_parts
        ),

        "\n".join(
            plain_parts
        )
    )


# ============================================================
# PROCESS CDC NOTICES
# ============================================================

def process_notices():

    notices = (
        fetch_notice_board()
    )


    # Dashboard always receives ALL
    # currently fetched notices.

    sorted_notices = sorted(

        notices,

        key=lambda item:
            get_numeric_id(
                item["id"]
            ),

        reverse=True
    )


    update_dashboard(

        notices=
            sorted_notices,

        notice_count=
            len(
                sorted_notices
            )
    )


    if not notices:

        print(
            "No CDC notices returned."
        )

        return


    state = (
        load_notice_state()
    )


    new_notices = (
        get_new_notices(
            notices,
            state
        )
    )


    if not new_notices:

        print(
            "No new CDC notices."
        )

        return


    print()
    print(
        "CDC notices to email:"
    )


    for notice in new_notices:

        print(

            f"  ID {notice['id']}: "
            f"{notice['subject']}"
        )


    # --------------------------------------------------------
    # IMPORTANT:
    # Update state ONLY after successful email.
    # --------------------------------------------------------

    send_notice_email(
        new_notices
    )


    highest_id = max(

        new_notices,

        key=lambda item:
            get_numeric_id(
                item["id"]
            )
    )["id"]


    state[
        "last_notified_id"
    ] = highest_id


    save_notice_state(
        state
    )


    print(
        "seen_notices.json updated."
    )


# ============================================================
# PROCESS PLACEMENTS
# ============================================================

def process_placements():

    placements = (
        fetch_placement_board()
    )


    # Dashboard receives ALL currently
    # fetched placement entries.

    update_dashboard(

        placements=
            placements,

        placement_count=
            len(
                placements
            )
    )


    state = (
        load_placement_state()
    )


    initialized = (
        state.get(
            "initialized",
            False
        )
    )


    seen_ids = {

        str(value)

        for value in state.get(
            "seen_ids",
            []
        )
    }


    new_placements = (
        get_new_placements(
            placements,
            state
        )
    )


    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------

    if not initialized:

        if not placements:

            print(
                "No placements available "
                "on first run."
            )

            return


        # Email only the newest 3.
        if new_placements:

            print()
            print(
                "First placement run:"
            )

            print(
                "Emailing:",
                len(new_placements)
            )

            send_placement_email(
                new_placements
            )


        # IMPORTANT:
        #
        # After successful email, mark EVERY
        # currently visible placement as seen.
        #
        # This prevents the remaining old entries
        # from generating emails on the next cycle.

        seen_ids = {

            str(
                placement["id"]
            )

            for placement in placements
        }


        state = {

            "initialized":
                True,

            "seen_ids":
                sorted(
                    seen_ids
                )
        }


        save_placement_state(
            state
        )


        print(
            "seen_placements.json initialized."
        )


        print(
            "Current placement IDs recorded:",
            len(seen_ids)
        )


        return


    # --------------------------------------------------------
    # SUBSEQUENT RUNS
    # --------------------------------------------------------

    if not new_placements:

        print(
            "No new placement entries."
        )

        return


    print()
    print(
        "New placement entries:"
    )


    for placement in new_placements:

        print(

            f"  ID {placement['id']}: "
            f"{placement['company']} - "
            f"{placement['designation']}"
        )


    # --------------------------------------------------------
    # Email first.
    # --------------------------------------------------------

    send_placement_email(
        new_placements
    )


    # --------------------------------------------------------
    # Only after successful email, mark them as seen.
    # --------------------------------------------------------

    for placement in new_placements:

        seen_ids.add(
            str(
                placement["id"]
            )
        )


    state = {

        "initialized":
            True,

        "seen_ids":
            sorted(
                seen_ids
            )
    }


    save_placement_state(
        state
    )


    print(
        "seen_placements.json updated."
    )


# ============================================================
# ONE MONITORING CYCLE
# ============================================================

def run_monitor_cycle():

    print()
    print("=" * 60)
    print("STARTING MONITORING CYCLE")
    print("=" * 60)

    update_dashboard(
        erp_status="Checking",
        last_check=current_time_string(),
        last_error=None
    )
    save_dashboard_data()

    try:
        # --------------------------------------------------------
        # CDC
        # --------------------------------------------------------
        print()
        print("=" * 60)
        print("CDC NOTICE BOARD")
        print("=" * 60)

        process_notices()
        save_dashboard_data()

        # --------------------------------------------------------
        # PLACEMENTS
        # --------------------------------------------------------
        print()
        print("=" * 60)
        print("PLACEMENT / INTERNSHIP BOARD")
        print("=" * 60)

        process_placements()

        # --------------------------------------------------------
        # Successful cycle
        # --------------------------------------------------------
        next_check_time = (
            datetime.now(IST)
            + timedelta(seconds=CHECK_INTERVAL_SECONDS)
        )

        next_check_string = next_check_time.strftime(
            "%d %b %Y, %I:%M:%S %p"
        )

        update_dashboard(
            erp_status="Connected",
            last_check=current_time_string(),
            next_check=next_check_string,
            last_error=None
        )
        save_dashboard_data()

        print()
        print("Monitoring cycle completed successfully.")

    except Exception as error:
        update_dashboard(
            erp_status="Error",
            last_error=str(error),
            next_check=None
        )
        save_dashboard_data()
        raise

