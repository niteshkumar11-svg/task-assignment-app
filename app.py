"""
TaskFlow — Team Task Manager
Streamlit + Google Sheets
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import uuid
import base64
from io import BytesIO

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

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

/* ── brand ── */
.tf-brand {
    display: flex; align-items: center; gap: 10px; margin-bottom: 2px;
}
.tf-logo {
    width: 38px; height: 38px; background: #2563EB; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
}
.tf-brand-name { font-size: 22px; font-weight: 700; color: #0F172A; letter-spacing: -.3px; }

/* ── login card ── */
.tf-login {
    background: white; border-radius: 16px;
    padding: 36px 32px 32px; border: 1.5px solid #E2E8F0;
    box-shadow: 0 8px 32px rgba(0,0,0,.09);
    margin-top: 8px;
}
.tf-login-h    { font-size: 20px; font-weight: 700; color: #0F172A; margin: 20px 0 4px; }
.tf-login-sub  { font-size: 13px; color: #64748B; margin-bottom: 20px; }

/* ── task card ── */
.tf-card {
    border: 1.5px solid #E2E8F0; border-radius: 12px;
    padding: 16px 18px 14px; margin-bottom: 4px; background: white;
    border-left-width: 4px; position: relative;
}
.tf-card-pending   { border-left-color: #2563EB; }
.tf-card-overdue   { border-left-color: #DC2626; }
.tf-card-completed { border-left-color: #059669; }

.tf-card-top {
    display: flex; justify-content: space-between;
    align-items: flex-start; gap: 12px; margin-bottom: 8px;
}
.tf-card-title {
    font-size: 15px; font-weight: 600; color: #0F172A;
    line-height: 1.4; word-break: break-word;
}
.tf-card-title.done { text-decoration: line-through; color: #94A3B8; }

.tf-pill {
    flex-shrink: 0; padding: 3px 10px; border-radius: 12px;
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
    white-space: nowrap;
}
.tf-pill-pending   { background: #EFF6FF; color: #2563EB; }
.tf-pill-overdue   { background: #FEF2F2; color: #DC2626; }
.tf-pill-completed { background: #ECFDF5; color: #059669; }

.tf-meta {
    font-size: 12px; color: #64748B; margin-bottom: 6px; line-height: 1.9;
}
.tf-desc {
    font-size: 13px; color: #475569; line-height: 1.6;
    border-top: 1px solid #F1F5F9; padding-top: 8px; margin-top: 2px;
}

/* ── filter radio pills ── */
div[data-testid="stHorizontalBlock"] .stRadio > label { display: none; }
.stRadio [role=radiogroup] { flex-direction: row !important; gap: 8px !important; flex-wrap: wrap; }
.stRadio label div[data-testid="stMarkdownContainer"] p {
    font-size: 12px !important; font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)


# ── GOOGLE SHEETS ──────────────────────────────────────────────────────────────
TASK_HEADERS = [
    "ID", "Title", "Description",
    "AssignedTo", "AssignedToName",
    "AssignedBy",  "AssignedByName",
    "Deadline", "Status", "CreatedAt", "CompletedAt", "Photo",
]


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
        raise


@st.cache_data(ttl=120, show_spinner=False)
def load_users() -> list[tuple[str, str]]:
    rows = get_ws("Users").get_all_records()
    return [
        (str(r.get("Email", "")).strip(), str(r.get("Name", "")).strip())
        for r in rows
        if r.get("Email") and r.get("Name") and "@" in str(r.get("Email", ""))
    ]


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


# ── SESSION ────────────────────────────────────────────────────────────────────
for key, default in [("logged_in", False), ("user_email", ""), ("user_name", "")]:
    if key not in st.session_state:
        st.session_state[key] = default


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
          <div class="tf-login-h">Sign in to continue</div>
          <div class="tf-login-sub">Select your account from the list below</div>
        </div>
        """, unsafe_allow_html=True)

        try:
            users = load_users()
            emails = [u[0] for u in users]
        except Exception as e:
            st.error(f"Could not load team list: {e}")
            users, emails = [], []

        sel = st.selectbox(
            "Email",
            ["— Select your email —"] + emails,
            label_visibility="collapsed",
        )

        if st.button("Sign In", type="primary", use_container_width=True):
            if sel == "— Select your email —":
                st.error("Please select your email")
            else:
                name = dict(users).get(sel, sel)
                st.session_state.logged_in  = True
                st.session_state.user_email = sel
                st.session_state.user_name  = name
                st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
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
    </p>
    """, unsafe_allow_html=True)
with right:
    if st.button("Sign out", use_container_width=True):
        st.session_state.logged_in  = False
        st.session_state.user_email = ""
        st.session_state.user_name  = ""
        st.rerun()

st.divider()

tab_assign, tab_view = st.tabs(["➕  Assign Task", "📋  My Tasks"])


# ══════════════════════════════════════════════════════════════════════════════
# ASSIGN TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_assign:
    st.subheader("Assign a New Task", divider="blue")

    try:
        users      = load_users()
        email_name = dict(users)
        email_list = [u[0] for u in users]
    except Exception as e:
        st.error(f"Could not load team members: {e}")
        users, email_name, email_list = [], {}, []

    with st.form("assign_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns(2)
        with c1:
            to_email = st.selectbox(
                "Assign to (email) *",
                ["— Select —"] + email_list,
            )
        with c2:
            st.text_input(
                "Assignee name",
                value=email_name.get(to_email, ""),
                disabled=True,
                help="Auto-filled from email",
            )

        title = st.text_input("Task title *", placeholder="Brief, clear title for this task")
        desc  = st.text_area(
            "Description",
            placeholder="Describe the task — steps, context, acceptance criteria…",
            height=130,
        )

        c3, c4 = st.columns(2)
        with c3:
            deadline = st.date_input(
                "Deadline *",
                value=date.today() + timedelta(days=3),
                min_value=date.today(),
                format="DD/MM/YYYY",
            )
        # c4 intentionally empty

        photo = st.file_uploader(
            "Reference photo (optional)",
            type=["jpg", "jpeg", "png", "gif"],
        )
        if photo:
            st.image(photo, caption="Preview", use_container_width=True)

        submitted = st.form_submit_button(
            "Assign Task", type="primary", use_container_width=True
        )

    # Validation + save (outside form so messages show cleanly)
    if submitted:
        errs = []
        if to_email == "— Select —": errs.append("Select who to assign this to")
        if not title.strip():        errs.append("Task title is required")
        if errs:
            for msg in errs:
                st.error(msg)
        else:
            with st.spinner("Saving task…"):
                save_task([
                    str(uuid.uuid4())[:8],
                    title.strip(),
                    desc.strip(),
                    to_email,
                    email_name.get(to_email, ""),
                    st.session_state.user_email,
                    st.session_state.user_name,
                    str(deadline),
                    "pending",
                    datetime.now().isoformat(timespec="seconds"),
                    "",
                    encode_photo(photo),
                ])
            assignee = email_name.get(to_email, to_email)
            st.success(f"Task assigned to **{assignee}**!")


# ══════════════════════════════════════════════════════════════════════════════
# MY TASKS TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_view:
    hdr_l, hdr_r = st.columns([3, 1])
    with hdr_l:
        st.subheader("My Tasks", divider="blue")
    with hdr_r:
        st.write("")
        if st.button("↺ Refresh", use_container_width=True):
            load_tasks.clear()
            st.rerun()

    # Load
    try:
        all_tasks = load_tasks()
        my_tasks  = [t for t in all_tasks
                     if t.get("AssignedTo") == st.session_state.user_email]
    except Exception as e:
        st.error(f"Could not load tasks: {e}")
        my_tasks = []

    if not my_tasks:
        st.info("No tasks assigned to you yet.")
        st.stop()

    # Counts for filter labels
    counts = {s: sum(1 for t in my_tasks if classify(t) == s)
              for s in ("pending", "overdue", "completed")}

    filt = st.radio(
        "Filter",
        options=[
            f"All ({len(my_tasks)})",
            f"Pending ({counts['pending']})",
            f"Overdue ({counts['overdue']})",
            f"Completed ({counts['completed']})",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )

    filt_key = filt.split()[0].lower()
    shown = (my_tasks if filt_key == "all"
             else [t for t in my_tasks if classify(t) == filt_key])

    # Sort: overdue first, then pending, then completed; within each by deadline asc
    _order = {"overdue": 0, "pending": 1, "completed": 2}
    shown.sort(key=lambda t: (_order.get(classify(t), 1), str(t.get("Deadline", ""))))

    if not shown:
        st.info(f"No {filt_key} tasks.")
        st.stop()

    # ── Render cards ──────────────────────────────────────────────────────────
    for task in shown:
        cls       = classify(task)
        done      = cls == "completed"
        title_cls = "done" if done else ""
        dl_str    = fmt_date(str(task.get("Deadline", "")))
        cr_str    = str(task.get("CreatedAt", ""))[:10]
        desc_html = (
            f'<div class="tf-desc">{task["Description"]}</div>'
            if task.get("Description") else ""
        )

        st.markdown(f"""
        <div class="tf-card tf-card-{cls}">
          <div class="tf-card-top">
            <div class="tf-card-title {title_cls}">{task.get('Title','')}</div>
            <span class="tf-pill tf-pill-{cls}">{cls}</span>
          </div>
          <div class="tf-meta">
            🕐 Deadline: <strong>{dl_str}</strong> &nbsp;·&nbsp;
            👤 From: {task.get('AssignedByName','')} &nbsp;·&nbsp;
            📅 Assigned: {cr_str}
          </div>
          {desc_html}
        </div>
        """, unsafe_allow_html=True)

        # Photo
        if task.get("Photo"):
            img_bytes = decode_photo(task["Photo"])
            if img_bytes:
                st.image(img_bytes, use_container_width=True)

        # Action row
        if not done:
            _, btn_col = st.columns([3, 1])
            with btn_col:
                if st.button(
                    "✅ Mark Complete",
                    key=f"done_{task['ID']}",
                    type="primary",
                    use_container_width=True,
                ):
                    with st.spinner("Updating…"):
                        finish_task(str(task["ID"]))
                    st.success("Marked as complete!")
                    st.rerun()
        else:
            done_at = str(task.get("CompletedAt", ""))[:10]
            st.caption(f"✓ Completed{' · ' + done_at if done_at else ''}")

        st.write("")  # card spacing
