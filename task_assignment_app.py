"""
TaskFlow — Team Task Manager
Streamlit + Google Sheets
Roles: owner > admin > user  |  Password auth  |  One active session per account
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import uuid, base64, threading, hashlib
from io import BytesIO

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
OWNER_EMAIL     = "nitesh.kumar11@flipkart.com"
ALLOWED_DOMAIN  = "flipkart.com"
SESSION_TTL_MIN = 60
PING_EVERY_S    = 300

TASK_HEADERS = [
    "ID", "Title", "Description",
    "AssignedTo", "AssignedToName",
    "AssignedBy", "AssignedByName",
    "Deadline", "Status", "CreatedAt", "CompletedAt", "Photo",
]
SESSION_HEADERS = ["Email", "SessionToken", "LoginAt", "LastSeen"]

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TaskFlow",
    page_icon="📋",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }

.block-container {
    max-width: 780px !important;
    padding-top: 2.5rem !important;
    padding-bottom: 4rem !important;
}

.tf-brand { display:flex; align-items:center; gap:10px; margin-bottom:2px; }
.tf-logo {
    width:38px; height:38px; background:#2563EB; border-radius:10px;
    display:flex; align-items:center; justify-content:center;
    font-size:20px; flex-shrink:0;
}
.tf-brand-name { font-size:22px; font-weight:700; color:#0F172A; letter-spacing:-.3px; }

.tf-login {
    background:white; border-radius:16px;
    padding:36px 32px 24px; border:1.5px solid #E2E8F0;
    box-shadow:0 8px 32px rgba(0,0,0,.09);
    margin-top:8px; margin-bottom:8px;
}
.tf-login-h   { font-size:20px; font-weight:700; color:#0F172A; margin:20px 0 4px; }
.tf-login-sub { font-size:13px; color:#64748B; margin-bottom:4px; }
.tf-who { font-size:13px; color:#1D4ED8; font-weight:600; background:#EFF6FF;
          border-radius:8px; padding:6px 12px; margin-bottom:16px; display:inline-block; }

.tf-role-owner { background:#7C3AED;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }
.tf-role-admin { background:#0F766E;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }
.tf-role-user  { background:#475569;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }

.tf-card {
    border:1.5px solid #E2E8F0; border-radius:12px;
    padding:16px 18px 14px; margin-bottom:4px; background:white;
    border-left-width:4px;
}
.tf-card-pending   { border-left-color:#2563EB; }
.tf-card-overdue   { border-left-color:#DC2626; }
.tf-card-completed { border-left-color:#059669; }

.tf-card-top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:8px; }
.tf-card-title { font-size:15px; font-weight:600; color:#0F172A; line-height:1.4; word-break:break-word; }
.tf-card-title.done { text-decoration:line-through; color:#94A3B8; }

.tf-pill { flex-shrink:0; padding:3px 10px; border-radius:12px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; white-space:nowrap; }
.tf-pill-pending   { background:#EFF6FF; color:#2563EB; }
.tf-pill-overdue   { background:#FEF2F2; color:#DC2626; }
.tf-pill-completed { background:#ECFDF5; color:#059669; }

.tf-meta { font-size:12px; color:#64748B; margin-bottom:6px; line-height:1.9; }
.tf-desc { font-size:13px; color:#475569; line-height:1.6; border-top:1px solid #F1F5F9; padding-top:8px; margin-top:2px; }
.tf-assignee-tag { display:inline-block; background:#EFF6FF; color:#1D4ED8; border-radius:8px; padding:2px 10px; font-size:12px; font-weight:600; margin-bottom:7px; }

.tf-online { display:inline-block; width:8px; height:8px; background:#10B981; border-radius:50%; margin-right:5px; }

div[data-testid="stHorizontalBlock"] .stRadio > label { display:none; }
.stRadio [role=radiogroup] { flex-direction:row !important; gap:8px !important; flex-wrap:wrap; }
.stRadio label div[data-testid="stMarkdownContainer"] p { font-size:12px !important; font-weight:500 !important; }

/* ── dashboard stat cards ── */
.tf-stat {
    background:white; border-radius:12px; border:1.5px solid #E2E8F0;
    padding:16px 10px 14px; text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.04);
}
.tf-stat-val   { font-size:30px; font-weight:800; line-height:1.15; }
.tf-stat-lbl   { font-size:10px; color:#64748B; font-weight:600;
                 text-transform:uppercase; letter-spacing:.06em; margin-top:4px; }
.tf-stat-blue  { color:#2563EB; }
.tf-stat-amber { color:#D97706; }
.tf-stat-red   { color:#DC2626; }
.tf-stat-green { color:#059669; }
.tf-stat-slate { color:#475569; }

/* ── user breakdown table ── */
.tf-table { width:100%; border-collapse:collapse; font-size:13px; }
.tf-table th { background:#F8FAFC; color:#64748B; font-size:11px; font-weight:600;
               text-transform:uppercase; letter-spacing:.05em;
               padding:8px 10px; text-align:left; border-bottom:2px solid #E2E8F0; }
.tf-table td { padding:10px 10px; border-bottom:1px solid #F1F5F9; color:#0F172A; vertical-align:middle; }
.tf-table tr:last-child td { border-bottom:none; }
.tf-table tr:hover td { background:#F8FAFC; }
.tf-bar-wrap { background:#F1F5F9; border-radius:4px; height:7px; overflow:hidden; width:80px; display:inline-block; }
.tf-bar-fill { height:100%; border-radius:4px; }
</style>
""", unsafe_allow_html=True)


# ── BROWSER-SESSION TOKEN ──────────────────────────────────────────────────────
if "session_token" not in st.session_state:
    st.session_state.session_token = str(uuid.uuid4())

MY_TOKEN = st.session_state.session_token


# ── GOOGLE SHEETS ──────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _gc():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def _ss():
    return _gc().open_by_key(st.secrets["spreadsheet_id"])


def get_ws(name: str):
    ss = _ss()
    try:
        return ss.worksheet(name)
    except gspread.WorksheetNotFound:
        if name == "Tasks":
            ws = ss.add_worksheet(title="Tasks", rows=2000, cols=len(TASK_HEADERS))
            ws.append_row(TASK_HEADERS)
            return ws
        if name == "Sessions":
            ws = ss.add_worksheet(title="Sessions", rows=500, cols=len(SESSION_HEADERS))
            ws.append_row(SESSION_HEADERS)
            return ws
        raise


# ── PASSWORD HELPERS ───────────────────────────────────────────────────────────
def _pw_hash(email: str, password: str) -> str:
    data = f"taskflow::{email.strip().lower()}::{password}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _pw_col(ws) -> int:
    """Return 1-based column index for Password, creating the header if absent."""
    headers = ws.row_values(1)
    if "Password" in headers:
        return headers.index("Password") + 1
    col = len(headers) + 1
    ws.update_cell(1, col, "Password")
    return col


def get_pw_hash(email: str) -> str:
    """Read the stored password hash directly (no cache — must be fresh)."""
    try:
        rows = get_ws("Users").get_all_records()
        for r in rows:
            if str(r.get("Email", "")).strip().lower() == email.lower():
                return str(r.get("Password", "")).strip()
    except Exception:
        pass
    return ""


def set_pw(email: str, password: str):
    """Write password hash to the Users sheet."""
    ws  = get_ws("Users")
    col = _pw_col(ws)
    try:
        cell = ws.find(email.strip().lower())
        ws.update_cell(cell.row, col, _pw_hash(email, password))
    except Exception:
        pass


def verify_pw(email: str, password: str) -> bool:
    stored = get_pw_hash(email)
    return bool(stored) and stored == _pw_hash(email, password)


def reset_pw(email: str):
    """Clear stored password so user must set a new one on next login."""
    ws  = get_ws("Users")
    col = _pw_col(ws)
    try:
        cell = ws.find(email.strip().lower())
        ws.update_cell(cell.row, col, "")
    except Exception:
        pass


# ── SESSION MANAGEMENT ─────────────────────────────────────────────────────────
def _session_age_min(s: str) -> float:
    try:
        return (datetime.now() - datetime.fromisoformat(str(s).strip())).total_seconds() / 60
    except Exception:
        return 9999.0


def check_session(email: str) -> tuple[bool, str]:
    try:
        for r in get_ws("Sessions").get_all_records():
            if str(r.get("Email", "")).strip() == email:
                if _session_age_min(r.get("LastSeen", "")) < SESSION_TTL_MIN:
                    return True, str(r.get("SessionToken", "")).strip()
    except Exception:
        pass
    return False, ""


def write_session(email: str, token: str):
    ws  = get_ws("Sessions")
    now = datetime.now().isoformat(timespec="seconds")
    try:
        cell = ws.find(email)
        ws.update(f"A{cell.row}:D{cell.row}", [[email, token, now, now]])
    except Exception:
        ws.append_row([email, token, now, now])


def _ping_bg(email: str, token: str):
    try:
        ws   = get_ws("Sessions")
        cell = ws.find(email)
        if cell and ws.row_values(cell.row)[1] == token:
            ws.update_cell(cell.row, 4, datetime.now().isoformat(timespec="seconds"))
    except Exception:
        pass


def ping_session(email: str, token: str):
    last = st.session_state.get("_last_ping")
    now  = datetime.now()
    if last and (now - last).total_seconds() < PING_EVERY_S:
        return
    st.session_state["_last_ping"] = now
    threading.Thread(target=_ping_bg, args=(email, token), daemon=True).start()


def remove_session(email: str):
    try:
        ws   = get_ws("Sessions")
        cell = ws.find(email)
        if cell:
            ws.delete_rows(cell.row)
    except Exception:
        pass


def get_all_sessions() -> dict[str, dict]:
    result = {}
    try:
        for r in get_ws("Sessions").get_all_records():
            email = str(r.get("Email", "")).strip()
            if not email:
                continue
            age = _session_age_min(r.get("LastSeen", ""))
            if age < SESSION_TTL_MIN:
                result[email] = {
                    "token":    str(r.get("SessionToken", "")),
                    "login_at": str(r.get("LoginAt", "")),
                    "age_min":  round(age, 1),
                }
    except Exception:
        pass
    return result


# ── USERS ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def load_users() -> list[tuple[str, str, str]]:
    rows   = get_ws("Users").get_all_records()
    result = []
    for r in rows:
        email = str(r.get("Email", "")).strip()
        name  = str(r.get("Name",  "")).strip()
        role  = str(r.get("Role",  "")).strip().lower() or "user"
        if email and name and "@" in email:
            if email == OWNER_EMAIL:
                role = "owner"
            result.append((email, name, role))
    return result


def _ensure_col(ws, header: str) -> int:
    headers = ws.row_values(1)
    if header in headers:
        return headers.index(header) + 1
    col = len(headers) + 1
    ws.update_cell(1, col, header)
    return col


def add_user(email: str, name: str) -> tuple[bool, str]:
    email = email.strip().lower()
    name  = name.strip()
    if not email:
        return False, "Email is required."
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        return False, f"Only @{ALLOWED_DOMAIN} email addresses are allowed."
    if not name:
        return False, "Name is required."
    if email in [u[0].lower() for u in load_users()]:
        return False, "This email is already registered."
    ws = get_ws("Users")
    _ensure_col(ws, "Role")
    _ensure_col(ws, "Password")
    ws.append_row([email, name, "user", ""], value_input_option="USER_ENTERED")
    load_users.clear()
    return True, f"{name} has been added. They will set their password on first sign in."


def set_user_role(email: str, new_role: str):
    ws  = get_ws("Users")
    col = _ensure_col(ws, "Role")
    try:
        cell = ws.find(email)
        if cell:
            ws.update_cell(cell.row, col, new_role)
            load_users.clear()
    except Exception:
        pass


# ── TASKS ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def load_tasks() -> list[dict]:
    return get_ws("Tasks").get_all_records()


def save_task(row: list):
    get_ws("Tasks").append_row(row, value_input_option="USER_ENTERED")
    load_tasks.clear()


def finish_task(task_id: str):
    ws   = get_ws("Tasks")
    cell = ws.find(task_id, in_column=1)
    if cell:
        ws.update_cell(cell.row, 9,  "completed")
        ws.update_cell(cell.row, 11, datetime.now().isoformat(timespec="seconds"))
        load_tasks.clear()


def delete_task(task_id: str):
    ws   = get_ws("Tasks")
    cell = ws.find(task_id, in_column=1)
    if cell:
        ws.delete_rows(cell.row)
        load_tasks.clear()


# ── PHOTO HELPERS ──────────────────────────────────────────────────────────────
# Google Sheets hard cell limit is 50,000 chars; stay safely under it.
_CELL_LIMIT = 40_000

def encode_photo(f) -> str:
    """
    Compress image progressively until base64 fits in a Sheets cell.
    Returns "" if PIL is unavailable or image cannot be compressed enough.
    """
    if not f or not PIL_OK:
        return ""
    try:
        img = Image.open(f).convert("RGB")
        # Each pass tries a smaller size / lower quality
        for max_px, quality in [
            (500, 60),
            (400, 50),
            (320, 40),
            (240, 32),
            (160, 25),
        ]:
            thumb = img.copy()
            thumb.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            buf = BytesIO()
            thumb.save(buf, format="JPEG", quality=quality, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            if len(b64) <= _CELL_LIMIT:
                return b64
        return ""   # couldn't compress enough; skip silently
    except Exception:
        return ""


def decode_photo(b64: str):
    try:
        return BytesIO(base64.b64decode(b64)) if b64 else None
    except Exception:
        return None


# ── TASK UTILS ─────────────────────────────────────────────────────────────────
def classify(task: dict) -> str:
    if str(task.get("Status", "")).lower() == "completed":
        return "completed"
    try:
        if datetime.strptime(str(task["Deadline"]), "%Y-%m-%d").date() < date.today():
            return "overdue"
    except Exception:
        pass
    return "pending"


def fmt_date(s: str) -> str:
    try:
        return datetime.strptime(str(s), "%Y-%m-%d").strftime("%d %b %Y")
    except Exception:
        return str(s)


def compute_stats(tasks: list[dict]) -> dict:
    today = date.today()
    pending = overdue = done_on_time = done_late = 0
    for t in tasks:
        status = str(t.get("Status", "")).lower()
        dl_str = str(t.get("Deadline", ""))
        ca_str = str(t.get("CompletedAt", "")).strip()
        if status == "completed":
            try:
                dl = datetime.strptime(dl_str, "%Y-%m-%d").date()
                ca = datetime.fromisoformat(ca_str).date() if ca_str else None
                if ca is None or ca <= dl:
                    done_on_time += 1
                else:
                    done_late += 1
            except Exception:
                done_on_time += 1
        else:
            try:
                if datetime.strptime(dl_str, "%Y-%m-%d").date() < today:
                    overdue += 1
                else:
                    pending += 1
            except Exception:
                pending += 1
    return {
        "total":        len(tasks),
        "pending":      pending,
        "overdue":      overdue,
        "done_on_time": done_on_time,
        "done_late":    done_late,
        "done_total":   done_on_time + done_late,
    }


# ── STREAMLIT SESSION DEFAULTS ─────────────────────────────────────────────────
for _k, _v in [
    ("logged_in",   False),
    ("user_email",  ""),
    ("user_name",   ""),
    ("user_role",   "user"),
    ("login_step",  "select"),   # select | password | set_password | conflict
    ("login_email", ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── PING ACTIVE SESSION ────────────────────────────────────────────────────────
if st.session_state.logged_in:
    ping_session(st.session_state.user_email, MY_TOKEN)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════════════
def _finish_login(email: str, users: list):
    """Set session state after successful auth and rerun."""
    user_map   = {u[0]: (u[1], u[2]) for u in users}
    name, role = user_map.get(email, (email, "user"))
    if email == OWNER_EMAIL:
        role = "owner"
    st.session_state.update({
        "logged_in":   True,
        "user_email":  email,
        "user_name":   name,
        "user_role":   role,
        "login_step":  "select",
        "login_email": "",
    })
    st.rerun()


if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.markdown("""
        <div class="tf-login">
          <div class="tf-brand">
            <div class="tf-logo">📋</div>
            <span class="tf-brand-name">TaskFlow</span>
          </div>
          <div class="tf-login-h">Welcome</div>
          <div class="tf-login-sub">Sign in or register a new team member</div>
        </div>
        """, unsafe_allow_html=True)

        login_tab, add_tab = st.tabs(["🔑  Sign In", "➕  Add User"])

        # ══ SIGN IN TAB ═══════════════════════════════════════════════════════
        with login_tab:
            try:
                users  = load_users()
                emails = [u[0] for u in users]
            except Exception as e:
                st.error(f"Could not load team list: {e}")
                users, emails = [], []

            step = st.session_state.login_step

            # ── STEP 1: select email  (Enter = Continue) ──────────────────────
            if step == "select":
                with st.form("login_select_form"):
                    sel  = st.selectbox(
                        "Your email",
                        ["— Select your email —"] + emails,
                        label_visibility="collapsed",
                    )
                    cont = st.form_submit_button(
                        "Continue →", type="primary", use_container_width=True
                    )
                if cont:
                    if sel == "— Select your email —":
                        st.error("Please select your email.")
                    else:
                        st.session_state.login_email = sel
                        st.session_state.login_step  = "set_password" if not get_pw_hash(sel) else "password"
                        st.rerun()

            # ── STEP 2a: first login — set password  (Enter = submit) ─────────
            elif step == "set_password":
                pending = st.session_state.login_email
                st.markdown(f'<div class="tf-who">👤 {pending}</div>', unsafe_allow_html=True)
                st.info("First sign in — please create your password for TaskFlow.")
                with st.form("set_pw_form"):
                    pw1  = st.text_input("New password",     type="password",
                                         placeholder="At least 6 characters")
                    pw2  = st.text_input("Confirm password", type="password",
                                         placeholder="Repeat the password")
                    save = st.form_submit_button(
                        "Set Password & Sign In", type="primary", use_container_width=True
                    )
                if st.button("← Back", key="back_spw", use_container_width=True):
                    st.session_state.login_step  = "select"
                    st.session_state.login_email = ""
                    st.rerun()
                if save:
                    if len(pw1) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif pw1 != pw2:
                        st.error("Passwords do not match.")
                    else:
                        with st.spinner("Saving password…"):
                            set_pw(pending, pw1)
                        if pending != OWNER_EMAIL:
                            active, old_tok = check_session(pending)
                            if active and old_tok != MY_TOKEN:
                                st.session_state.login_step = "conflict"
                                st.rerun()
                        write_session(pending, MY_TOKEN)
                        _finish_login(pending, users)

            # ── STEP 2b: returning login — verify password  (Enter = Sign In) ─
            elif step == "password":
                pending = st.session_state.login_email
                st.markdown(f'<div class="tf-who">👤 {pending}</div>', unsafe_allow_html=True)
                with st.form("login_pw_form"):
                    pw   = st.text_input("Password", type="password",
                                         placeholder="Enter your TaskFlow password")
                    sign = st.form_submit_button(
                        "Sign In", type="primary", use_container_width=True
                    )
                if st.button("← Back", key="back_pw", use_container_width=True):
                    st.session_state.login_step  = "select"
                    st.session_state.login_email = ""
                    st.rerun()
                if sign:
                    if not pw:
                        st.error("Please enter your password.")
                    elif not verify_pw(pending, pw):
                        st.error("Incorrect password. Please try again.")
                    else:
                        if pending != OWNER_EMAIL:
                            active, old_tok = check_session(pending)
                            if active and old_tok != MY_TOKEN:
                                st.session_state.login_step = "conflict"
                                st.rerun()
                        write_session(pending, MY_TOKEN)
                        _finish_login(pending, users)

            # ── STEP 3: session conflict ──────────────────────────────────────
            elif step == "conflict":
                pending = st.session_state.login_email
                st.markdown(
                    f'<div class="tf-who">👤 {pending}</div>',
                    unsafe_allow_html=True,
                )
                st.error(
                    "**This account is already signed in from another device or browser.**\n\n"
                    "Click **Force Sign In** to log out that session and sign in here."
                )
                fc1, fc2 = st.columns(2)
                with fc1:
                    if st.button("Force Sign In", type="primary", use_container_width=True):
                        with st.spinner("Clearing other session…"):
                            remove_session(pending)
                            write_session(pending, MY_TOKEN)
                        _finish_login(pending, users)
                with fc2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.login_step  = "select"
                        st.session_state.login_email = ""
                        st.rerun()

        # ══ ADD USER TAB ══════════════════════════════════════════════════════
        with add_tab:
            st.caption(f"Only @{ALLOWED_DOMAIN} addresses can be registered.")
            new_email = st.text_input("Email ID",  placeholder=f"name@{ALLOWED_DOMAIN}", key="reg_email")
            new_name  = st.text_input("Full Name", placeholder="Enter full name",         key="reg_name")
            if st.button("Add User", type="primary", use_container_width=True, key="reg_btn"):
                ok, msg = add_user(new_email, new_name)
                (st.success if ok else st.error)(msg)

    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
role     = st.session_state.user_role
is_owner = role == "owner"
is_admin = role in ("owner", "admin")

# ── Header ────────────────────────────────────────────────────────────────────
left, right = st.columns([4, 1])
with left:
    st.markdown(f"""
    <div class="tf-brand">
      <div class="tf-logo">📋</div>
      <span class="tf-brand-name">TaskFlow</span>
    </div>
    <p style="font-size:13px;color:#64748B;margin:2px 0 0">
      Signed in as <strong>{st.session_state.user_name}</strong>
      &nbsp;·&nbsp; {st.session_state.user_email}
      &nbsp;&nbsp;<span class="tf-role-{role}">{role}</span>
    </p>
    """, unsafe_allow_html=True)
with right:
    if st.button("Sign out", use_container_width=True):
        remove_session(st.session_state.user_email)
        st.session_state.update({
            "logged_in":   False,
            "user_email":  "",
            "user_name":   "",
            "user_role":   "user",
            "login_step":  "select",
            "login_email": "",
        })
        st.rerun()

st.divider()

# ── Tabs (vary by role) ───────────────────────────────────────────────────────
if is_owner:
    tab_dash, tab_assign, tab_view, tab_manage = st.tabs([
        "🏠  Dashboard",
        "➕  Assign Task",
        "📋  All Tasks",
        "⚙️  Manage Users",
    ])
elif is_admin:
    tab_dash, tab_assign, tab_view = st.tabs([
        "🏠  Dashboard",
        "➕  Assign Task",
        "📋  All Tasks",
    ])
    tab_manage = None
else:
    # Regular users: no Assign Task tab
    tab_dash, tab_view = st.tabs([
        "🏠  Dashboard",
        "📋  My Tasks",
    ])
    tab_assign = None
    tab_manage = None


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.subheader("Dashboard", divider="blue")

    try:
        dash_tasks = load_tasks()
        dash_users = load_users()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        dash_tasks, dash_users = [], []

    name_map  = {u[0]: u[1] for u in dash_users}   # email → name
    all_names = sorted({u[1] for u in dash_users})  # unique display names

    # ── User selector — available to everyone ─────────────────────────────────
    if all_names:
        sel_name = st.selectbox(
            "View stats for",
            ["All Users"] + all_names,
            index=0,
            key="dash_person",
        )
        if sel_name == "All Users":
            filtered = dash_tasks
        else:
            filtered = [t for t in dash_tasks
                        if t.get("AssignedToName") == sel_name]
    else:
        sel_name = "All Users"
        filtered = dash_tasks

    st.write("")

    # ── Stat cards ────────────────────────────────────────────────────────────
    s = compute_stats(filtered)

    on_time_pct = (
        round(s["done_on_time"] / s["done_total"] * 100)
        if s["done_total"] > 0 else 0
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, val, lbl, cls in [
        (c1, s["total"],        "Total Tasks",       "tf-stat-slate"),
        (c2, s["pending"],      "Pending",            "tf-stat-blue"),
        (c3, s["overdue"],      "Overdue",            "tf-stat-red"),
        (c4, s["done_on_time"], "Completed On Time",  "tf-stat-green"),
        (c5, s["done_late"],    "Completed Late",     "tf-stat-amber"),
    ]:
        with col:
            st.markdown(
                f'<div class="tf-stat">'
                f'<div class="tf-stat-val {cls}">{val}</div>'
                f'<div class="tf-stat-lbl">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.write("")

    # ── On-time rate bar ──────────────────────────────────────────────────────
    if s["done_total"] > 0:
        bar_color = "#059669" if on_time_pct >= 70 else "#D97706" if on_time_pct >= 40 else "#DC2626"
        st.markdown(
            f'<div style="font-size:13px;color:#475569;margin-bottom:6px;">'
            f'On-time completion rate: '
            f'<strong style="color:{bar_color}">{on_time_pct}%</strong>'
            f' &nbsp;({s["done_on_time"]} of {s["done_total"]} completed tasks)</div>'
            f'<div style="background:#F1F5F9;border-radius:6px;height:10px;overflow:hidden;">'
            f'<div style="background:{bar_color};width:{on_time_pct}%;height:100%;'
            f'border-radius:6px;transition:width .3s;"></div></div>',
            unsafe_allow_html=True,
        )
        st.write("")

    # ── Per-user breakdown (all roles, All Users view) ───────────────────────
    if sel_name == "All Users" and dash_users:
        st.markdown("#### Breakdown by Team Member")

        rows_html = ""
        for u_email, u_name, _ in sorted(dash_users, key=lambda u: u[1]):
            u_tasks = [t for t in dash_tasks if t.get("AssignedTo") == u_email]
            if not u_tasks:
                continue
            us = compute_stats(u_tasks)
            pct = round(us["done_on_time"] / us["done_total"] * 100) if us["done_total"] > 0 else 0
            bar_col = "#059669" if pct >= 70 else "#D97706" if pct >= 40 else "#DC2626"
            bar_w   = pct
            pct_cell = (
                f'<span style="font-size:12px;color:{bar_col};font-weight:700">{pct}%</span>'
                f'&nbsp;<div class="tf-bar-wrap">'
                f'<div class="tf-bar-fill" style="width:{bar_w}%;background:{bar_col}"></div>'
                f'</div>'
                if us["done_total"] > 0 else
                f'<span style="color:#94A3B8;font-size:12px;">—</span>'
            )
            rows_html += (
                f"<tr>"
                f"<td><strong>{u_name}</strong></td>"
                f"<td style='text-align:center'>{us['total']}</td>"
                f"<td style='text-align:center;color:#2563EB'>{us['pending']}</td>"
                f"<td style='text-align:center;color:#DC2626'>{us['overdue']}</td>"
                f"<td style='text-align:center;color:#059669'>{us['done_on_time']}</td>"
                f"<td style='text-align:center;color:#D97706'>{us['done_late']}</td>"
                f"<td>{pct_cell}</td>"
                f"</tr>"
            )

        if rows_html:
            st.markdown(
                f'<table class="tf-table">'
                f'<thead><tr>'
                f'<th>Team Member</th>'
                f'<th style="text-align:center">Total</th>'
                f'<th style="text-align:center">Pending</th>'
                f'<th style="text-align:center">Overdue</th>'
                f'<th style="text-align:center">Done On Time</th>'
                f'<th style="text-align:center">Done Late</th>'
                f'<th>On-Time Rate</th>'
                f'</tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                f'</table>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No tasks assigned yet.")

    # ── Upcoming / pending tasks preview for selected person ─────────────────
    elif filtered:
        pending_tasks = [t for t in filtered if classify(t) in ("pending", "overdue")]
        pending_tasks.sort(key=lambda t: str(t.get("Deadline", "")))

        if pending_tasks:
            st.markdown(f"#### Upcoming Tasks ({len(pending_tasks)})")
            for t in pending_tasks[:5]:
                cls          = classify(t)
                assignee_lbl = f' · <span style="color:#64748B">→ {t.get("AssignedToName","")}</span>'
                st.markdown(
                    f'<div class="tf-card tf-card-{cls}" style="margin-bottom:8px">'
                    f'<div class="tf-card-top">'
                    f'<span class="tf-card-title">{t.get("Title","")}</span>'
                    f'<span class="tf-pill tf-pill-{cls}">{cls}</span>'
                    f'</div>'
                    f'<div class="tf-meta">🕐 {fmt_date(str(t.get("Deadline","")))} {assignee_lbl}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if len(pending_tasks) > 5:
                st.caption(f"+ {len(pending_tasks) - 5} more — see the My Tasks tab for the full list.")


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN TAB  (admin / owner only — tab_assign is None for regular users)
# ══════════════════════════════════════════════════════════════════════════════
if tab_assign is not None:
 with tab_assign:
    st.subheader("Assign a New Task", divider="blue")

    try:
        users      = load_users()
        email_name = {u[0]: u[1] for u in users}
        email_list = [u[0] for u in users]
    except Exception as e:
        st.error(f"Could not load team members: {e}")
        users, email_name, email_list = [], {}, []

    # Email + name OUTSIDE the form so the name updates immediately on selection
    c1, c2 = st.columns(2)
    with c1:
        to_email = st.selectbox("Assign to (email) *", ["— Select —"] + email_list,
                                key="assign_to_email")
    with c2:
        st.text_input("Assignee name", value=email_name.get(to_email, ""),
                      disabled=True, help="Auto-filled from email")

    with st.form("assign_form", clear_on_submit=True, border=False):
        title = st.text_input("Task title *", placeholder="Brief, clear title for this task")
        desc  = st.text_area("Description",
                             placeholder="Describe the task — steps, context, acceptance criteria…",
                             height=130)
        c3, _ = st.columns(2)
        with c3:
            deadline = st.date_input("Deadline *",
                                     value=date.today() + timedelta(days=3),
                                     min_value=date.today(), format="DD/MM/YYYY")
        photo = st.file_uploader("Reference photo (optional)", type=["jpg", "jpeg", "png", "gif"])
        if photo:
            st.image(photo, caption="Preview", use_container_width=True)

        submitted = st.form_submit_button("Assign Task", type="primary", use_container_width=True)

    if submitted:
        errs = []
        if to_email == "— Select —": errs.append("Select who to assign this to")
        if not title.strip():        errs.append("Task title is required")
        if errs:
            for msg in errs: st.error(msg)
        else:
            with st.spinner("Saving task…"):
                photo_b64   = encode_photo(photo)
                photo_skipped = photo is not None and not photo_b64
                try:
                    save_task([
                        str(uuid.uuid4())[:8], title.strip(), desc.strip(),
                        to_email, email_name.get(to_email, ""),
                        st.session_state.user_email, st.session_state.user_name,
                        str(deadline), "pending",
                        datetime.now().isoformat(timespec="seconds"), "",
                        photo_b64,
                    ])
                except Exception as e:
                    st.error(f"Could not save task: {e}")
                    st.stop()
            assignee = email_name.get(to_email, to_email)
            st.success(f"Task assigned to **{assignee}**!")
            if photo_skipped:
                st.warning("Photo was too large to store even after compression — task saved without it. Try a smaller image.")


# ══════════════════════════════════════════════════════════════════════════════
# TASKS TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_view:
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.subheader("All Tasks" if is_admin else "My Tasks", divider="blue")
    with hdr_r:
        st.write("")
        if st.button("↺ Refresh", use_container_width=True):
            load_tasks.clear()
            st.rerun()

    try:
        all_tasks = load_tasks()
        visible   = (all_tasks if is_admin
                     else [t for t in all_tasks
                           if t.get("AssignedTo") == st.session_state.user_email])
    except Exception as e:
        st.error(f"Could not load tasks: {e}")
        visible = []

    if not visible:
        st.info("No tasks yet." if is_admin else "No tasks assigned to you yet.")
    else:
        if is_admin:
            assignees = sorted({t.get("AssignedToName", "") for t in visible if t.get("AssignedToName")})
            chosen    = st.selectbox("Show tasks for", ["Everyone"] + assignees, key="person_filter")
            if chosen != "Everyone":
                visible = [t for t in visible if t.get("AssignedToName") == chosen]

        counts = {s: sum(1 for t in visible if classify(t) == s)
                  for s in ("pending", "overdue", "completed")}

        filt = st.radio("Filter", options=[
            f"All ({len(visible)})",
            f"Pending ({counts['pending']})",
            f"Overdue ({counts['overdue']})",
            f"Completed ({counts['completed']})",
        ], horizontal=True, label_visibility="collapsed")

        filt_key = filt.split()[0].lower()
        shown    = (visible if filt_key == "all"
                    else [t for t in visible if classify(t) == filt_key])

        _order = {"overdue": 0, "pending": 1, "completed": 2}
        shown.sort(key=lambda t: (_order.get(classify(t), 1), str(t.get("Deadline", ""))))

        if not shown:
            st.info(f"No {filt_key} tasks.")
        else:
            for task in shown:
                tid       = str(task.get("ID", ""))
                cls       = classify(task)
                done      = cls == "completed"
                title_cls = "done" if done else ""
                dl_str    = fmt_date(str(task.get("Deadline", "")))
                cr_str    = str(task.get("CreatedAt", ""))[:10]
                desc_html = (f'<div class="tf-desc">{task["Description"]}</div>'
                             if task.get("Description") else "")
                assignee_html = (
                    f'<div class="tf-assignee-tag">👤 {task.get("AssignedToName", task.get("AssignedTo",""))}</div>'
                    if is_admin else ""
                )

                st.markdown(f"""
                <div class="tf-card tf-card-{cls}">
                  {assignee_html}
                  <div class="tf-card-top">
                    <div class="tf-card-title {title_cls}">{task.get('Title','')}</div>
                    <span class="tf-pill tf-pill-{cls}">{cls}</span>
                  </div>
                  <div class="tf-meta">
                    🕐 Deadline: <strong>{dl_str}</strong> &nbsp;·&nbsp;
                    📤 From: {task.get('AssignedByName','')} &nbsp;·&nbsp;
                    📅 Assigned: {cr_str}
                  </div>
                  {desc_html}
                </div>
                """, unsafe_allow_html=True)

                if task.get("Photo"):
                    img_data = decode_photo(task["Photo"])
                    if img_data:
                        st.image(img_data, use_container_width=True)

                confirm_key = f"del_confirm_{tid}"

                if st.session_state.get(confirm_key):
                    st.warning("⚠️ Delete this task permanently?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("Yes, Delete", key=f"del_yes_{tid}",
                                     type="primary", use_container_width=True):
                            with st.spinner("Deleting…"):
                                delete_task(tid)
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    with dc2:
                        if st.button("Cancel", key=f"del_no_{tid}", use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()

                elif not done:
                    if is_admin:
                        _, done_col, del_col = st.columns([2, 2, 1])
                        with done_col:
                            if st.button("✅ Mark Complete", key=f"done_{tid}",
                                         type="primary", use_container_width=True):
                                with st.spinner("Updating…"):
                                    finish_task(tid)
                                st.success("Marked as complete!")
                                st.rerun()
                        with del_col:
                            if st.button("🗑️", key=f"del_{tid}",
                                         use_container_width=True, help="Delete task"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                    else:
                        _, btn_col = st.columns([3, 1])
                        with btn_col:
                            if st.button("✅ Mark Complete", key=f"done_{tid}",
                                         type="primary", use_container_width=True):
                                with st.spinner("Updating…"):
                                    finish_task(tid)
                                st.success("Marked as complete!")
                                st.rerun()
                else:
                    done_at = str(task.get("CompletedAt", ""))[:10]
                    if is_admin:
                        _, del_col = st.columns([4, 1])
                        with del_col:
                            if st.button("🗑️", key=f"del_{tid}",
                                         use_container_width=True, help="Delete task"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                    st.caption(f"✓ Completed{' · ' + done_at if done_at else ''}")

                st.write("")


# ══════════════════════════════════════════════════════════════════════════════
# MANAGE USERS TAB  (owner only)
# ══════════════════════════════════════════════════════════════════════════════
if is_owner and tab_manage is not None:
    with tab_manage:
        st.subheader("Manage Users", divider="blue")

        mu1, mu2 = st.tabs(["👥  Users & Roles", "🔌  Active Sessions"])

        # ── Users & Roles ─────────────────────────────────────────────────────
        with mu1:
            st.caption("Promote users to Admin or reset their password.")
            try:
                all_users = load_users()
            except Exception as e:
                st.error(f"Could not load users: {e}")
                all_users = []

            if not all_users:
                st.info("No users found.")
            else:
                for u_email, u_name, u_role in all_users:
                    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
                    with c1:
                        st.markdown(f"**{u_name}**  \n`{u_email}`")
                    with c2:
                        st.markdown(f'<span class="tf-role-{u_role}">{u_role}</span>',
                                    unsafe_allow_html=True)
                    with c3:
                        if u_email == OWNER_EMAIL:
                            st.caption("owner — fixed")
                        else:
                            new_role = st.selectbox(
                                "Role", options=["user", "admin"],
                                index=1 if u_role == "admin" else 0,
                                key=f"sel_{u_email}",
                                label_visibility="collapsed",
                            )
                    with c4:
                        if u_email != OWNER_EMAIL:
                            if st.button("Save", key=f"save_{u_email}"):
                                with st.spinner("…"):
                                    set_user_role(u_email, new_role)
                                st.success(f"Updated → {new_role}")
                                st.rerun()
                    with c5:
                        if st.button("Reset PW", key=f"rpw_{u_email}",
                                     help="Force user to set a new password on next login"):
                            with st.spinner("…"):
                                reset_pw(u_email)
                            st.success(f"Password reset for {u_name}.")
                            st.rerun()

                    st.divider()

        # ── Active Sessions ───────────────────────────────────────────────────
        with mu2:
            st.caption("Users with an active session in the last 60 minutes.")
            if st.button("↺ Refresh", key="refresh_sess"):
                st.rerun()

            sessions = get_all_sessions()
            if not sessions:
                st.info("No active sessions right now.")
            else:
                user_name_map = {u[0]: u[1] for u in load_users()}
                for s_email, info in sessions.items():
                    s_name    = user_name_map.get(s_email, s_email)
                    is_me     = s_email == st.session_state.user_email
                    age_label = f"{int(info['age_min'])} min ago" if info['age_min'] >= 1 else "just now"

                    sc1, sc2 = st.columns([4, 1])
                    with sc1:
                        me_tag = " **(you)**" if is_me else ""
                        st.markdown(
                            f'<span class="tf-online"></span>'
                            f'**{s_name}**{me_tag}  \n'
                            f'`{s_email}` · last seen {age_label}',
                            unsafe_allow_html=True,
                        )
                    with sc2:
                        if not is_me:
                            if st.button("Sign out", key=f"kick_{s_email}"):
                                with st.spinner(f"Signing out {s_name}…"):
                                    remove_session(s_email)
                                st.success(f"{s_name} signed out.")
                                st.rerun()
                    st.divider()
