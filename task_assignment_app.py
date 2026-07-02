"""
TaskFlow — Team Task Manager
Streamlit + Google Sheets
Roles: owner > admin > user  |  One active session per account
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import uuid, base64, threading
from io import BytesIO

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
OWNER_EMAIL     = "nitesh.kumar11@flipkart.com"
ALLOWED_DOMAIN  = "flipkart.com"
SESSION_TTL_MIN = 60    # session expires after 60 min of inactivity
PING_EVERY_S    = 300   # ping the sheet every 5 min max

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

/* brand */
.tf-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 2px; }
.tf-logo {
    width: 38px; height: 38px; background: #2563EB; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.tf-brand-name { font-size: 22px; font-weight: 700; color: #0F172A; letter-spacing: -.3px; }

/* login card */
.tf-login {
    background: white; border-radius: 16px;
    padding: 36px 32px 20px; border: 1.5px solid #E2E8F0;
    box-shadow: 0 8px 32px rgba(0,0,0,.09);
    margin-top: 8px; margin-bottom: 8px;
}
.tf-login-h   { font-size: 20px; font-weight: 700; color: #0F172A; margin: 20px 0 4px; }
.tf-login-sub { font-size: 13px; color: #64748B; margin-bottom: 4px; }

/* role badges */
.tf-role-owner { background:#7C3AED;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }
.tf-role-admin { background:#0F766E;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }
.tf-role-user  { background:#475569;color:white;padding:2px 9px;border-radius:8px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em; }

/* task card */
.tf-card {
    border: 1.5px solid #E2E8F0; border-radius: 12px;
    padding: 16px 18px 14px; margin-bottom: 4px; background: white;
    border-left-width: 4px;
}
.tf-card-pending   { border-left-color: #2563EB; }
.tf-card-overdue   { border-left-color: #DC2626; }
.tf-card-completed { border-left-color: #059669; }

.tf-card-top {
    display: flex; justify-content: space-between;
    align-items: flex-start; gap: 12px; margin-bottom: 8px;
}
.tf-card-title { font-size: 15px; font-weight: 600; color: #0F172A; line-height: 1.4; word-break: break-word; }
.tf-card-title.done { text-decoration: line-through; color: #94A3B8; }

.tf-pill { flex-shrink:0; padding:3px 10px; border-radius:12px; font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; white-space:nowrap; }
.tf-pill-pending   { background:#EFF6FF; color:#2563EB; }
.tf-pill-overdue   { background:#FEF2F2; color:#DC2626; }
.tf-pill-completed { background:#ECFDF5; color:#059669; }

.tf-meta { font-size:12px; color:#64748B; margin-bottom:6px; line-height:1.9; }
.tf-desc { font-size:13px; color:#475569; line-height:1.6; border-top:1px solid #F1F5F9; padding-top:8px; margin-top:2px; }
.tf-assignee-tag { display:inline-block; background:#EFF6FF; color:#1D4ED8; border-radius:8px; padding:2px 10px; font-size:12px; font-weight:600; margin-bottom:7px; }

/* online dot */
.tf-online { display:inline-block; width:8px; height:8px; background:#10B981; border-radius:50%; margin-right:5px; }

/* filter radio */
div[data-testid="stHorizontalBlock"] .stRadio > label { display:none; }
.stRadio [role=radiogroup] { flex-direction:row !important; gap:8px !important; flex-wrap:wrap; }
.stRadio label div[data-testid="stMarkdownContainer"] p { font-size:12px !important; font-weight:500 !important; }
</style>
""", unsafe_allow_html=True)


# ── UNIQUE BROWSER-SESSION TOKEN ───────────────────────────────────────────────
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


# ── SESSION MANAGEMENT ─────────────────────────────────────────────────────────
def _session_age_min(last_seen_str: str) -> float:
    try:
        dt = datetime.fromisoformat(str(last_seen_str).strip())
        return (datetime.now() - dt).total_seconds() / 60
    except Exception:
        return 9999.0


def check_session(email: str) -> tuple[bool, str]:
    """Returns (is_active, existing_token). Active = last seen within SESSION_TTL_MIN."""
    try:
        rows = get_ws("Sessions").get_all_records()
        for r in rows:
            if str(r.get("Email", "")).strip() == email:
                age = _session_age_min(r.get("LastSeen", ""))
                if age < SESSION_TTL_MIN:
                    return True, str(r.get("SessionToken", "")).strip()
    except Exception:
        pass
    return False, ""


def write_session(email: str, token: str):
    ws      = get_ws("Sessions")
    now_str = datetime.now().isoformat(timespec="seconds")
    try:
        cell = ws.find(email)
        row  = cell.row
        ws.update(f"A{row}:D{row}", [[email, token, now_str, now_str]])
    except Exception:
        ws.append_row([email, token, now_str, now_str])


def _ping_bg(email: str, token: str):
    try:
        ws   = get_ws("Sessions")
        cell = ws.find(email)
        if cell:
            row = ws.row_values(cell.row)
            if len(row) > 1 and row[1] == token:
                ws.update_cell(cell.row, 4, datetime.now().isoformat(timespec="seconds"))
    except Exception:
        pass


def ping_session(email: str, token: str):
    """Fire-and-forget: update LastSeen at most once per PING_EVERY_S seconds."""
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
    """Returns {email: {token, login_at, last_seen, age_min}} for active sessions."""
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
                    "last_seen":str(r.get("LastSeen", "")),
                    "age_min":  round(age, 1),
                }
    except Exception:
        pass
    return result


# ── USERS ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30, show_spinner=False)
def load_users() -> list[tuple[str, str, str]]:
    """Returns [(email, name, role), ...]."""
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


def _ensure_role_col(ws) -> int:
    headers = ws.row_values(1)
    if "Role" in headers:
        return headers.index("Role") + 1
    col = len(headers) + 1
    ws.update_cell(1, col, "Role")
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
    _ensure_role_col(ws)
    ws.append_row([email, name, "user"], value_input_option="USER_ENTERED")
    load_users.clear()
    return True, f"{name} has been added to the system."


def set_user_role(email: str, new_role: str):
    ws       = get_ws("Users")
    role_col = _ensure_role_col(ws)
    cell     = ws.find(email)
    if cell:
        ws.update_cell(cell.row, role_col, new_role)
        load_users.clear()


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
def encode_photo(f) -> str:
    if not f:
        return ""
    try:
        if PIL_OK:
            img = Image.open(f)
            img.thumbnail((900, 700), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=72)
            return base64.b64encode(buf.getvalue()).decode()
        return base64.b64encode(f.read()).decode()
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


# ── STREAMLIT SESSION DEFAULTS ─────────────────────────────────────────────────
for _k, _v in [
    ("logged_in",  False),
    ("user_email", ""),
    ("user_name",  ""),
    ("user_role",  "user"),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── PING ACTIVE SESSION ────────────────────────────────────────────────────────
if st.session_state.logged_in:
    ping_session(st.session_state.user_email, MY_TOKEN)


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════════════
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

        # ── Sign In ───────────────────────────────────────────────────────────
        with login_tab:
            try:
                users  = load_users()
                emails = [u[0] for u in users]
            except Exception as e:
                st.error(f"Could not load team list: {e}")
                users, emails = [], []

            # ── Session conflict state ────────────────────────────────────────
            conflict = st.session_state.get("login_conflict", "")

            if conflict:
                st.error(
                    f"**{conflict}** is already signed in from another device or browser.\n\n"
                    "If this is you, click **Force Sign In** to log out the other session."
                )
                fc1, fc2 = st.columns(2)
                with fc1:
                    if st.button("Force Sign In", type="primary", use_container_width=True):
                        with st.spinner("Clearing other session…"):
                            remove_session(conflict)
                            write_session(conflict, MY_TOKEN)
                        user_map     = {u[0]: (u[1], u[2]) for u in users}
                        name, role   = user_map.get(conflict, (conflict, "user"))
                        if conflict == OWNER_EMAIL:
                            role = "owner"
                        st.session_state.logged_in  = True
                        st.session_state.user_email = conflict
                        st.session_state.user_name  = name
                        st.session_state.user_role  = role
                        st.session_state.pop("login_conflict", None)
                        st.rerun()
                with fc2:
                    if st.button("Cancel", use_container_width=True):
                        st.session_state.pop("login_conflict", None)
                        st.rerun()

            else:
                sel = st.selectbox(
                    "Email",
                    ["— Select your email —"] + emails,
                    label_visibility="collapsed",
                )
                if st.button("Sign In", type="primary", use_container_width=True):
                    if sel == "— Select your email —":
                        st.error("Please select your email.")
                    else:
                        # Owner bypasses session check; everyone else is verified
                        if sel != OWNER_EMAIL:
                            active, old_token = check_session(sel)
                            if active and old_token != MY_TOKEN:
                                st.session_state["login_conflict"] = sel
                                st.rerun()

                        # No conflict (or owner) — proceed
                        with st.spinner("Signing in…"):
                            write_session(sel, MY_TOKEN)
                        user_map   = {u[0]: (u[1], u[2]) for u in users}
                        name, role = user_map.get(sel, (sel, "user"))
                        if sel == OWNER_EMAIL:
                            role = "owner"
                        st.session_state.logged_in  = True
                        st.session_state.user_email = sel
                        st.session_state.user_name  = name
                        st.session_state.user_role  = role
                        st.rerun()

        # ── Add User ──────────────────────────────────────────────────────────
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
        for k in ("logged_in", "user_email", "user_name", "user_role"):
            st.session_state[k] = False if k == "logged_in" else ""
        st.rerun()

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
if is_owner:
    tab_assign, tab_view, tab_manage = st.tabs([
        "➕  Assign Task",
        "📋  All Tasks",
        "⚙️  Manage Users",
    ])
else:
    tab_assign, tab_view = st.tabs([
        "➕  Assign Task",
        "📋  All Tasks" if is_admin else "📋  My Tasks",
    ])
    tab_manage = None


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_assign:
    st.subheader("Assign a New Task", divider="blue")

    try:
        users      = load_users()
        email_name = {u[0]: u[1] for u in users}
        email_list = [u[0] for u in users]
    except Exception as e:
        st.error(f"Could not load team members: {e}")
        users, email_name, email_list = [], {}, []

    with st.form("assign_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns(2)
        with c1:
            to_email = st.selectbox("Assign to (email) *", ["— Select —"] + email_list)
        with c2:
            st.text_input("Assignee name", value=email_name.get(to_email, ""),
                          disabled=True, help="Auto-filled from email")

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
                save_task([
                    str(uuid.uuid4())[:8], title.strip(), desc.strip(),
                    to_email, email_name.get(to_email, ""),
                    st.session_state.user_email, st.session_state.user_name,
                    str(deadline), "pending",
                    datetime.now().isoformat(timespec="seconds"), "",
                    encode_photo(photo),
                ])
            st.success(f"Task assigned to **{email_name.get(to_email, to_email)}**!")


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
            assignees     = sorted({t.get("AssignedToName", "") for t in visible if t.get("AssignedToName")})
            chosen_person = st.selectbox("Show tasks for", ["Everyone"] + assignees, key="person_filter")
            if chosen_person != "Everyone":
                visible = [t for t in visible if t.get("AssignedToName") == chosen_person]

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

                # ── Action row ────────────────────────────────────────────────
                confirm_key = f"del_confirm_{tid}"

                if st.session_state.get(confirm_key):
                    # Deletion confirmation
                    st.warning("⚠️ Delete this task permanently?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("Yes, Delete", key=f"del_yes_{tid}", type="primary", use_container_width=True):
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
                        # Admin / Owner: complete + delete
                        _, done_col, del_col = st.columns([2, 2, 1])
                        with done_col:
                            if st.button("✅ Mark Complete", key=f"done_{tid}", type="primary", use_container_width=True):
                                with st.spinner("Updating…"):
                                    finish_task(tid)
                                st.success("Marked as complete!")
                                st.rerun()
                        with del_col:
                            if st.button("🗑️", key=f"del_{tid}", use_container_width=True, help="Delete task"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                    else:
                        # Regular user: complete only
                        _, btn_col = st.columns([3, 1])
                        with btn_col:
                            if st.button("✅ Mark Complete", key=f"done_{tid}", type="primary", use_container_width=True):
                                with st.spinner("Updating…"):
                                    finish_task(tid)
                                st.success("Marked as complete!")
                                st.rerun()

                else:
                    done_at = str(task.get("CompletedAt", ""))[:10]
                    # Admin/Owner: completed tasks can still be deleted
                    if is_admin:
                        _, del_col = st.columns([4, 1])
                        with del_col:
                            if st.button("🗑️", key=f"del_{tid}", use_container_width=True, help="Delete task"):
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

        mu_tab1, mu_tab2 = st.tabs(["👥  Users & Roles", "🔌  Active Sessions"])

        # ── Users & Roles ─────────────────────────────────────────────────────
        with mu_tab1:
            st.caption("Promote users to Admin (can see all tasks). Only you can change roles.")

            try:
                all_users = load_users()
            except Exception as e:
                st.error(f"Could not load users: {e}")
                all_users = []

            if not all_users:
                st.info("No users found in the sheet.")
            else:
                for u_email, u_name, u_role in all_users:
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
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
                                with st.spinner("Saving…"):
                                    set_user_role(u_email, new_role)
                                st.success(f"Updated {u_name} → {new_role}")
                                st.rerun()
                    st.divider()

        # ── Active Sessions ───────────────────────────────────────────────────
        with mu_tab2:
            st.caption("Users with an active session in the last 60 minutes.")
            if st.button("↺ Refresh sessions", key="refresh_sess"):
                st.rerun()

            sessions = get_all_sessions()
            if not sessions:
                st.info("No active sessions right now.")
            else:
                for s_email, info in sessions.items():
                    user_map  = {u[0]: u[1] for u in load_users()}
                    s_name    = user_map.get(s_email, s_email)
                    is_me     = (s_email == st.session_state.user_email)
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
                            if st.button("Sign out", key=f"kick_{s_email}", help=f"Force sign out {s_name}"):
                                with st.spinner(f"Signing out {s_name}…"):
                                    remove_session(s_email)
                                st.success(f"{s_name} has been signed out.")
                                st.rerun()
                    st.divider()
