import streamlit as st
import sqlite3
import hashlib
import secrets
import string
from pathlib import Path
from datetime import date, datetime

st.set_page_config(page_title="FarmGuard", page_icon="🌱", layout="wide")

DB_PATH = Path(__file__).parent / "farmguard.db"
LOGO_PATH = Path(__file__).parent / "assets" / "farmguard_logo.png"

st.markdown("""
<style>
.stApp {
    background: #f6f8f3;
}

[data-testid="stSidebar"] {
    background: #eaf1e5;
}

h1, h2, h3 {
    color: #244b35;
}

.stButton>button,
.stFormSubmitButton>button {
    background: #2f6b45;
    color: white;
    border: 0;
    border-radius: 9px;
    font-weight: 600;
}

.stButton>button:hover,
.stFormSubmitButton>button:hover {
    background: #245638;
    color: white;
}

/* SIDEBAR NAVIGATION BUTTONS */
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    text-align: left;
    justify-content: flex-start;
    border-radius: 9px;
    padding: 10px 13px;
    margin: 3px 0;
    font-weight: 600;
    transition: 0.2s ease;
}

/* SELECTED NAVIGATION */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #dcebdd;
    color: #245638;
    border: 1px solid #c5ddc8;
}

/* UNSELECTED NAVIGATION */
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: transparent;
    color: #365b42;
    border: 1px solid transparent;
}

/* HOVER EFFECT */
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: #dcebdd;
    color: #245638;
    border-color: #c5ddc8;
}

/* SIDEBAR CAPTIONS */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: #55745c;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS fg_farms (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          farm_code TEXT UNIQUE NOT NULL,
          farm_name TEXT NOT NULL,
          owner_name TEXT NOT NULL,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fg_workers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          farm_id INTEGER NOT NULL,
          worker_code TEXT NOT NULL,
          worker_name TEXT NOT NULL,
          pin_hash TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL,
          UNIQUE(farm_id,worker_code),
          FOREIGN KEY(farm_id) REFERENCES fg_farms(id)
        );

        CREATE TABLE IF NOT EXISTS fg_reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          farm_id INTEGER NOT NULL,
          worker_id INTEGER,
          crop_type TEXT NOT NULL,
          crop_name TEXT NOT NULL,
          location TEXT NOT NULL,
          section TEXT,
          report_date TEXT NOT NULL,
          symptoms TEXT NOT NULL,
          severity TEXT NOT NULL,
          affected_area REAL NOT NULL,
          notes TEXT,
          status TEXT NOT NULL DEFAULT 'Pending',
          created_at TEXT NOT NULL,
          FOREIGN KEY(farm_id) REFERENCES fg_farms(id),
          FOREIGN KEY(worker_id) REFERENCES fg_workers(id)
        );
        """)


# ---------------- SECURITY ----------------

def make_hash(value, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        value.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32
    )
    return salt.hex() + "$" + digest.hex()


def check_hash(value, saved):
    try:
        salt = bytes.fromhex(saved.split("$")[0])
        return secrets.compare_digest(make_hash(value, salt), saved)
    except (ValueError, AttributeError):
        return False


def code(prefix):
    chars = string.ascii_uppercase + string.digits
    return prefix + "-" + "".join(
        secrets.choice(chars) for _ in range(6)
    )


# ---------------- FARM FUNCTIONS ----------------

def register_farm(name, owner, username, password):
    farm_code = code("FG")

    with connect() as con:
        cur = con.execute(
            """INSERT INTO fg_farms
            (farm_code,farm_name,owner_name,username,password_hash,created_at)
            VALUES(?,?,?,?,?,?)""",
            (
                farm_code,
                name.strip(),
                owner.strip(),
                username.strip().lower(),
                make_hash(password),
                datetime.now().isoformat(timespec="seconds")
            )
        )
        farm_id = cur.lastrowid

    return farm_id, farm_code


def get_farm(username):
    with connect() as con:
        return con.execute(
            "SELECT * FROM fg_farms WHERE username=?",
            (username.strip().lower(),)
        ).fetchone()


# ---------------- REPORT FUNCTIONS ----------------

def get_reports(farm_id):
    with connect() as con:
        return con.execute("""
          SELECT r.*, COALESCE(w.worker_name,'Farm Owner') reporter
          FROM fg_reports r
          LEFT JOIN fg_workers w ON r.worker_id=w.id
          WHERE r.farm_id=?
          ORDER BY r.report_date DESC,r.id DESC
        """, (farm_id,)).fetchall()


def add_report(farm_id, worker_id, values):
    with connect() as con:
        con.execute("""INSERT INTO fg_reports
          (farm_id,worker_id,crop_type,crop_name,location,section,
           report_date,symptoms,severity,affected_area,notes,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          (
              farm_id,
              worker_id,
              values["crop_type"],
              values["crop_name"],
              values["location"],
              values["section"],
              str(values["report_date"]),
              values["symptoms"],
              values["severity"],
              values["affected_area"],
              values["notes"],
              datetime.now().isoformat(timespec="seconds")
          )
        )


def set_status(farm_id, report_id, status):
    with connect() as con:
        con.execute(
            "UPDATE fg_reports SET status=? WHERE id=? AND farm_id=?",
            (status, report_id, farm_id)
        )


# ---------------- WORKER FUNCTIONS ----------------

def get_workers(farm_id):
    with connect() as con:
        return con.execute("""
          SELECT * FROM fg_workers
          WHERE farm_id=?
          ORDER BY worker_name
        """, (farm_id,)).fetchall()


def add_worker(farm_id, name, pin):
    worker_code = code("WK")

    with connect() as con:
        con.execute("""INSERT INTO fg_workers
          (farm_id,worker_code,worker_name,pin_hash,created_at)
          VALUES(?,?,?,?,?)""",
          (
              farm_id,
              worker_code,
              name.strip(),
              make_hash(pin),
              datetime.now().isoformat(timespec="seconds")
          )
        )

    return worker_code


def set_worker_active(farm_id, worker_id, active):
    with connect() as con:
        con.execute(
            "UPDATE fg_workers SET active=? WHERE id=? AND farm_id=?",
            (int(active), worker_id, farm_id)
        )


# ---------------- INITIALIZATION ----------------

init_db()

if "fg_user" not in st.session_state:
    st.session_state.fg_user = None

if "fg_owner_page" not in st.session_state:
    st.session_state.fg_owner_page = "Dashboard"


# ---------------- SIDEBAR BRANDING ----------------

if LOGO_PATH.exists():
    st.sidebar.image(str(LOGO_PATH), use_container_width=True)
else:
    st.sidebar.markdown("## 🌱 FarmGuard")

st.sidebar.caption("CROP HEALTH MONITORING SYSTEM")


# ==================================================
# LOGIN / REGISTRATION
# ==================================================

if st.session_state.fg_user is None:

    st.title("FarmGuard")
    st.write("Crop monitoring and inspection reporting for your farm.")

    owner_tab, worker_tab, register_tab = st.tabs(
        ["Owner Login", "Worker Login", "Register Farm"]
    )

    # ---------------- OWNER LOGIN ----------------

    with owner_tab:

        with st.form("owner_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            go = st.form_submit_button(
                "Log In",
                use_container_width=True
            )

        if go:
            farm = get_farm(username)

            if farm and check_hash(password, farm["password_hash"]):
                st.session_state.fg_user = {
                    "role": "owner",
                    "farm": dict(farm)
                }
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    # ---------------- WORKER LOGIN ----------------

    with worker_tab:

        st.caption(
            "Ask the farm owner for your Farm ID, Worker Code, and PIN."
        )

        with st.form("worker_login"):
            farm_code = st.text_input("Farm ID")
            worker_code = st.text_input("Worker Code")
            pin = st.text_input("PIN", type="password")

            go = st.form_submit_button(
                "Log In",
                use_container_width=True
            )

        if go:

            with connect() as con:

                farm = con.execute(
                    "SELECT * FROM fg_farms WHERE farm_code=?",
                    (farm_code.strip().upper(),)
                ).fetchone()

                worker = None

                if farm:
                    worker = con.execute("""
                        SELECT * FROM fg_workers
                        WHERE farm_id=? AND worker_code=? AND active=1
                    """, (
                        farm["id"],
                        worker_code.strip().upper()
                    )).fetchone()

            if farm and worker and check_hash(pin, worker["pin_hash"]):

                st.session_state.fg_user = {
                    "role": "worker",
                    "farm": dict(farm),
                    "worker": dict(worker)
                }

                st.rerun()

            else:
                st.error(
                    "Invalid login details, or worker account is inactive."
                )

    # ---------------- REGISTER FARM ----------------

    with register_tab:

        st.write("Create the owner account for your farm.")

        with st.form("farm_register"):

            farm_name = st.text_input("Farm Name")
            owner_name = st.text_input("Owner Name")
            new_username = st.text_input("Create Username")
            new_password = st.text_input(
                "Create Password",
                type="password"
            )
            confirm = st.text_input(
                "Confirm Password",
                type="password"
            )

            go = st.form_submit_button(
                "Register Farm",
                use_container_width=True
            )

        if go:

            if not all([
                farm_name.strip(),
                owner_name.strip(),
                new_username.strip(),
                new_password
            ]):
                st.error("Please complete all fields.")

            elif len(new_password) < 8:
                st.error("Password must have at least 8 characters.")

            elif new_password != confirm:
                st.error("Passwords do not match.")

            else:

                try:

                    farm_id, farm_code = register_farm(
                        farm_name,
                        owner_name,
                        new_username,
                        new_password
                    )

                    st.success("Farm account created.")

                    st.info(
                        f"Your Farm ID is **{farm_code}**. "
                        "Keep it safe and share it only with your workers."
                    )

                    with connect() as con:
                        farm = con.execute(
                            "SELECT * FROM fg_farms WHERE id=?",
                            (farm_id,)
                        ).fetchone()

                    st.session_state.fg_user = {
                        "role": "owner",
                        "farm": dict(farm)
                    }

                    st.rerun()

                except sqlite3.IntegrityError:
                    st.error("That username is already in use.")


# ==================================================
# LOGGED-IN WORKSPACE
# ==================================================

else:

    user = st.session_state.fg_user
    farm = user["farm"]
    farm_id = farm["id"]
    role = user["role"]

    st.sidebar.divider()

    st.sidebar.write(f"**Farm:** {farm['farm_name']}")
    st.sidebar.write(f"**Farm ID:** `{farm['farm_code']}`")

    # ==================================================
    # OWNER NAVIGATION WITH MATERIAL ICONS
    # ==================================================

    if role == "owner":

        st.sidebar.caption(f"Owner: {farm['owner_name']}")

        st.sidebar.divider()
        st.sidebar.caption("MAIN NAVIGATION")

        owner_pages = [
            ("Dashboard", ":material/dashboard:"),
            ("Farm Records", ":material/grass:"),
            ("Inspection Prioritization", ":material/format_list_numbered:"),
            ("Inspection Management", ":material/assignment_turned_in:"),
            ("Worker Management", ":material/groups:"),
            ("About", ":material/info:")
        ]

        for label, icon in owner_pages:

            is_selected = (
                st.session_state.fg_owner_page == label
            )

            if st.sidebar.button(
                label,
                key=f"owner_nav_{label}",
                icon=icon,
                type="primary" if is_selected else "secondary",
                use_container_width=True
            ):
                st.session_state.fg_owner_page = label
                st.rerun()

        page = st.session_state.fg_owner_page

    # ==================================================
    # WORKER NAVIGATION
    # ==================================================

    else:

        st.sidebar.caption(
            f"Worker: {user['worker']['worker_name']}"
        )

        pages = [
            "Submit Crop Report",
            "My Reports",
            "About"
        ]

        page = st.sidebar.radio("Navigation", pages)

    # ---------------- LOG OUT ----------------

    if st.sidebar.button(
        "Log Out",
        use_container_width=True
    ):
        st.session_state.fg_user = None
        st.session_state.fg_owner_page = "Dashboard"
        st.rerun()

    reports = get_reports(farm_id)


    # ==================================================
    # WORKER: SUBMIT CROP REPORT
    # ==================================================

    if role == "worker" and page == "Submit Crop Report":

        st.title("Submit Crop Report")
        st.write(
            "Report damaged or unhealthy crops to the farm owner."
        )

        with st.form("crop_report", clear_on_submit=True):

            crop_type = st.selectbox(
                "Crop Type",
                [
                    "Rice",
                    "Mango",
                    "Banana",
                    "Coconut",
                    "Corn",
                    "Vegetable",
                    "Other"
                ]
            )

            crop_name = st.text_input("Crop Name / Variety")
            location = st.text_input("Farm / Field Location")
            section = st.text_input("Section / Row / Tree ID")

            report_date = st.date_input(
                "Date Observed",
                value=date.today()
            )

            symptoms = st.text_area(
                "Observed Damage or Symptoms"
            )

            severity = st.select_slider(
                "Severity",
                ["Low", "Moderate", "High", "Critical"]
            )

            affected_area = st.number_input(
                "Estimated Affected Area (%)",
                0.0,
                100.0,
                0.0,
                1.0
            )

            notes = st.text_area(
                "Additional Notes (Optional)"
            )

            submit = st.form_submit_button(
                "Submit Report",
                use_container_width=True
            )

        if submit:

            if not crop_name.strip() or not location.strip() or not symptoms.strip():

                st.error(
                    "Please enter the crop name, location, and observed symptoms."
                )

            else:

                add_report(
                    farm_id,
                    user["worker"]["id"],
                    {
                        "crop_type": crop_type,
                        "crop_name": crop_name.strip(),
                        "location": location.strip(),
                        "section": section.strip(),
                        "report_date": report_date,
                        "symptoms": symptoms.strip(),
                        "severity": severity,
                        "affected_area": affected_area,
                        "notes": notes.strip()
                    }
                )

                st.success(
                    "Report submitted. The farm owner can now review it."
                )


    # ==================================================
    # WORKER: MY REPORTS
    # ==================================================

    elif role == "worker" and page == "My Reports":

        st.title("My Submitted Reports")

        mine = [
            r for r in reports
            if r["worker_id"] == user["worker"]["id"]
        ]

        if not mine:
            st.info("You have not submitted any reports yet.")

        for r in mine:

            with st.expander(
                f"{r['crop_name']} • {r['report_date']} • {r['status']}"
            ):

                st.write(
                    f"**Location:** {r['location']} — "
                    f"{r['section'] or 'No section specified'}"
                )

                st.write(f"**Symptoms:** {r['symptoms']}")
                st.write(f"**Severity:** {r['severity']}")
                st.write(f"**Affected area:** {r['affected_area']}%")
                st.write(f"**Status:** {r['status']}")

                if r["notes"]:
                    st.write(f"**Notes:** {r['notes']}")


    # ==================================================
    # OWNER: DASHBOARD
    # ==================================================

    elif role == "owner" and page == "Dashboard":

        # ---------------- DASHBOARD HEADER ----------------
        st.title("Crop Monitoring Overview")
        st.caption("Monitor crop conditions and prioritize farm inspections.")

        total_observations = len(reports)
        pending = sum(r["status"] == "Pending" for r in reports)
        inspected = sum(r["status"] == "Inspected" for r in reports)
        high_priority = sum(
            r["severity"] in ("High", "Critical") for r in reports
        )

        # ---------------- OVERVIEW CARDS ----------------
        # Professional inline SVG icons keep the dashboard consistent
        # without relying on emoji rendering or external icon packages.
        dashboard_icons = {
            "observations": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M11 21v-8.5C6.5 12.5 3.5 9.5 3.5 5
                           c4.5 0 7.5 3 7.5 7.5" />
                  <path d="M11 15c0-4.5 3-7.5 7.5-7.5
                           0 4.5-3 7.5-7.5 7.5" />
                  <path d="M11 21h8" />
                </svg>
            """,
            "pending": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8 4h8l2 2v14H6V4h2Z" />
                  <path d="M9 4V2h6v2M9 10h6M9 14h6M9 18h3" />
                </svg>
            """,
            "priority": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3 2.8 19a1.4 1.4 0 0 0 1.2 2h16
                           a1.4 1.4 0 0 0 1.2-2L12 3Z" />
                  <path d="M12 9v5M12 17.5h.01" />
                </svg>
            """,
            "inspected": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M8 4h8l2 2v14H6V4h2Z" />
                  <path d="M9 4V2h6v2M9 12l2 2 4-4" />
                </svg>
            """
        }

        def dashboard_metric(column, icon_svg, value, label, accent, tint):
            column.markdown(
                f"""<div style='display:flex;align-items:center;gap:15px;
                background:#ffffff;border:1px solid #e5eadf;
                border-radius:14px;padding:19px 20px;min-height:124px;
                box-shadow:0 2px 8px rgba(34,72,43,.045);'>
                  <div style='width:46px;height:46px;min-width:46px;
                      display:flex;align-items:center;justify-content:center;
                      border-radius:12px;background:{tint};color:{accent};'>
                    <span style='display:flex;width:25px;height:25px;
                        align-items:center;justify-content:center;'>
                      <style>
                        .fg-dashboard-icon svg {{
                          width:25px;height:25px;fill:none;
                          stroke:currentColor;stroke-width:1.8;
                          stroke-linecap:round;stroke-linejoin:round;
                        }}
                      </style>
                      <span class='fg-dashboard-icon'>{icon_svg}</span>
                    </span>
                  </div>
                  <div style='min-width:0;'>
                    <div style='font-size:29px;font-weight:700;
                        color:#202820;line-height:1.15;'>{value}</div>
                    <div style='font-size:14px;font-weight:500;
                        color:#778078;margin-top:7px;'>{label}</div>
                  </div>
                </div>""",
                unsafe_allow_html=True
            )

        left, right = st.columns(2, gap="medium")
        dashboard_metric(
            left, dashboard_icons["observations"], total_observations,
            "Total Observations", "#287544", "#edf5ef"
        )
        dashboard_metric(
            right, dashboard_icons["pending"], pending,
            "Pending Inspections", "#b87932", "#fbf3e9"
        )

        left, right = st.columns(2, gap="medium")
        dashboard_metric(
            left, dashboard_icons["priority"], high_priority,
            "High Priority", "#c64d45", "#fbefee"
        )
        dashboard_metric(
            right, dashboard_icons["inspected"], inspected,
            "Inspected", "#287544", "#edf5ef"
        )

        st.markdown("### Crop Health Trends")
        st.caption("A summary of submitted crop observations and their reported condition.")

        if reports:
            chart_left, chart_right = st.columns([1.15, 1], gap="large")

            # Reports submitted by date
            date_counts = {}
            for report in reports:
                report_day = str(report["report_date"])
                date_counts[report_day] = date_counts.get(report_day, 0) + 1

            sorted_dates = sorted(date_counts.items())
            trend_data = {
                "Date": [day for day, _ in sorted_dates],
                "Observations": [count for _, count in sorted_dates]
            }

            with chart_left:
                with st.container(border=True):
                    st.markdown("**Observation Activity**")
                    st.caption("Number of reports submitted per date")
                    st.line_chart(
                        trend_data,
                        x="Date",
                        y="Observations",
                        use_container_width=True
                    )

            # Crop category distribution
            crop_counts = {}
            for report in reports:
                crop = report["crop_type"] or "Other"
                crop_counts[crop] = crop_counts.get(crop, 0) + 1

            with chart_right:
                with st.container(border=True):
                    st.markdown("**Observations by Crop Type**")
                    st.caption("Distribution of reported crops")
                    crop_chart_data = {
                        "Crop Type": list(sorted(crop_counts.keys())),
                        "Observations": [crop_counts[crop] for crop in sorted(crop_counts.keys())]
                    }
                    st.bar_chart(
                        crop_chart_data,
                        x="Crop Type",
                        y="Observations",
                        use_container_width=True
                    )

            # Severity overview
            severity_order = ["Low", "Moderate", "High", "Critical"]
            severity_counts = {
                level: sum(r["severity"] == level for r in reports)
                for level in severity_order
            }
            st.markdown("**Reported Crop Condition**")
            severity_cols = st.columns(4)
            severity_colors = {
                "Low": "#2f8f57",
                "Moderate": "#d6a52b",
                "High": "#e47b35",
                "Critical": "#d94b4b"
            }
            for col, level in zip(severity_cols, severity_order):
                col.markdown(
                    f"""<div style='background:#ffffff;border:1px solid #e8ece5;
                    border-radius:10px;padding:12px 14px;text-align:center;'>
                    <div style='font-size:22px;font-weight:700;color:{severity_colors[level]};'>
                    {severity_counts[level]}</div>
                    <div style='font-size:13px;color:#68736a;'>{level}</div></div>""",
                    unsafe_allow_html=True
                )

        else:
            st.info("No crop observations yet. Submit a crop report to start building your dashboard trends.")

        # ---------------- RECENT REPORTS ----------------
        st.markdown("### Latest Field Observations")
        if reports:
            st.dataframe(
                [{
                    "Date": r["report_date"],
                    "Crop": r["crop_name"],
                    "Crop Type": r["crop_type"],
                    "Location": r["location"],
                    "Severity": r["severity"],
                    "Reported By": r["reporter"],
                    "Status": r["status"]
                } for r in reports[:8]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No reports yet. Add a worker or submit a crop observation.")


    # ==================================================
    # OWNER: FARM RECORDS
    # ==================================================

    elif role == "owner" and page == "Farm Records":

        st.title("Farm Records")

        search = st.text_input(
            "Search crop, field, reporter, or symptoms"
        )

        status_filter = st.selectbox(
            "Filter Status",
            ["All", "Pending", "Inspected"]
        )

        filtered = reports

        if status_filter != "All":
            filtered = [
                r for r in filtered
                if r["status"] == status_filter
            ]

        if search.strip():

            q = search.lower()

            filtered = [
                r for r in filtered
                if q in " ".join(
                    str(r[k])
                    for k in [
                        "crop_name",
                        "crop_type",
                        "location",
                        "reporter",
                        "symptoms"
                    ]
                ).lower()
            ]

        if not filtered:
            st.info("No matching records.")

        for r in filtered:

            with st.expander(
                f"#{r['id']} • {r['crop_name']} • "
                f"{r['report_date']} • {r['status']}"
            ):

                st.write(
                    f"**Crop:** {r['crop_type']} — {r['crop_name']}"
                )

                st.write(
                    f"**Location:** {r['location']} / "
                    f"{r['section'] or '—'}"
                )

                st.write(f"**Symptoms:** {r['symptoms']}")

                st.write(
                    f"**Severity:** {r['severity']} | "
                    f"**Affected area:** {r['affected_area']}%"
                )

                st.write(f"**Reported by:** {r['reporter']}")
                st.write(f"**Notes:** {r['notes'] or '—'}")

                new_status = st.selectbox(
                    "Inspection Status",
                    ["Pending", "Inspected"],
                    index=0 if r["status"] == "Pending" else 1,
                    key=f"status_{r['id']}"
                )

                if st.button(
                    "Save Status",
                    key=f"save_{r['id']}"
                ):

                    set_status(
                        farm_id,
                        r["id"],
                        new_status
                    )

                    st.success("Status updated.")
                    st.rerun()


    # ==================================================
    # OWNER: INSPECTION PRIORITIZATION
    # ==================================================

    elif role == "owner" and page == "Inspection Prioritization":

        st.title("Inspection Prioritization")

        st.write(
            "A simple priority score based on severity and affected area."
        )

        severity_score = {
            "Low": 25,
            "Moderate": 50,
            "High": 75,
            "Critical": 100
        }

        ranked = []

        for r in reports:

            score = (
                0.6 * severity_score[r["severity"]]
                + 0.4 * float(r["affected_area"])
            )

            ranked.append((score, r))

        ranked.sort(
            key=lambda x: x[0],
            reverse=True
        )

        st.caption(
            "Priority score = 60% severity + 40% affected area. "
            "Use this as a guide for inspection, not as a disease diagnosis."
        )

        if ranked:

            st.dataframe(
                [{
                    "Rank": i + 1,
                    "Crop": r["crop_name"],
                    "Location": r["location"],
                    "Severity": r["severity"],
                    "Affected Area (%)": r["affected_area"],
                    "Score": round(score, 1),
                    "Status": r["status"]
                } for i, (score, r) in enumerate(ranked)],
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("No reports to prioritize.")


    # ==================================================
    # OWNER: INSPECTION MANAGEMENT
    # ==================================================

    elif role == "owner" and page == "Inspection Management":

        st.title("Inspection Management")

        pending_rows = [
            r for r in reports
            if r["status"] == "Pending"
        ]

        st.metric(
            "Pending Inspections",
            len(pending_rows)
        )

        if not pending_rows:
            st.success(
                "All submitted reports have been inspected."
            )

        for r in pending_rows:

            with st.container(border=True):

                st.write(
                    f"**{r['crop_name']}** — {r['location']}"
                )

                st.caption(
                    f"{r['report_date']} • {r['severity']} • "
                    f"Reported by {r['reporter']}"
                )

                if st.button(
                    "Mark as Inspected",
                    key=f"inspect_{r['id']}"
                ):

                    set_status(
                        farm_id,
                        r["id"],
                        "Inspected"
                    )

                    st.rerun()


    # ==================================================
    # OWNER: WORKER MANAGEMENT
    # ==================================================

    elif role == "owner" and page == "Worker Management":

        st.title("Worker Management")

        st.write(
            "Create an individual account for each farm worker."
        )

        with st.form(
            "create_worker",
            clear_on_submit=True
        ):

            worker_name = st.text_input("Worker Name")

            pin = st.text_input(
                "Create PIN (at least 6 characters)",
                type="password"
            )

            confirm_pin = st.text_input(
                "Confirm PIN",
                type="password"
            )

            create = st.form_submit_button(
                "Create Worker Account"
            )

        if create:

            if not worker_name.strip():

                st.error("Enter the worker's name.")

            elif len(pin) < 6:

                st.error("PIN must be at least 6 characters.")

            elif pin != confirm_pin:

                st.error("PINs do not match.")

            else:

                worker_code = add_worker(
                    farm_id,
                    worker_name,
                    pin
                )

                st.success("Worker account created.")

                st.info(
                    f"Give this worker their login details:\n\n"
                    f"Farm ID: **{farm['farm_code']}**\n\n"
                    f"Worker Code: **{worker_code}**\n\n"
                    f"PIN: **{pin}**"
                )

                st.warning(
                    "Save these credentials securely. "
                    "The PIN will not be shown again."
                )

        st.subheader("Registered Workers")

        workers = get_workers(farm_id)

        if not workers:
            st.info("No workers registered yet.")

        for w in workers:

            with st.container(border=True):

                left, right = st.columns([3, 1])

                left.write(f"**{w['worker_name']}**")

                left.caption(
                    f"{w['worker_code']} • "
                    f"{'Active' if w['active'] else 'Inactive'}"
                )

                if w["active"]:

                    if right.button(
                        "Deactivate",
                        key=f"off_{w['id']}"
                    ):

                        set_worker_active(
                            farm_id,
                            w["id"],
                            False
                        )

                        st.rerun()

                else:

                    if right.button(
                        "Activate",
                        key=f"on_{w['id']}"
                    ):

                        set_worker_active(
                            farm_id,
                            w["id"],
                            True
                        )

                        st.rerun()


    # ==================================================
    # ABOUT
    # ==================================================

    elif page == "About":

        st.title("About FarmGuard")

        st.write(
            "FarmGuard helps farm owners and workers record crop "
            "conditions, review reports, and organize field inspections."
        )

        st.info(
            "FarmGuard organizes observations and supports inspection "
            "planning. It does not diagnose crop diseases or prescribe treatments."
        )

        st.caption(
            "Technology: Python, Streamlit, and SQLite."
        )