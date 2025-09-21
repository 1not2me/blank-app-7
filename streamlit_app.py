# streamlit_app.py
# -*- coding: utf-8 -*-
import csv
import re
from io import BytesIO
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# =========================
# הגדרות כלליות
# =========================
st.set_page_config(page_title="שאלון לסטודנטים – תשפ״ו", layout="centered")

# ====== עיצוב (CSS אחיד כפי שביקשת) ======
st.markdown("""
<style>
:root{
  --ink:#0f172a; 
  --muted:#475569; 
  --ring:rgba(99,102,241,.25); 
  --card:rgba(255,255,255,.85);
}
html, body, [class*="css"] { font-family: system-ui, "Segoe UI", Arial; }
.stApp, .main, [data-testid="stSidebar"]{ direction:rtl; text-align:right; }
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 600px at 8% 8%, #e0f7fa 0%, transparent 65%),
    radial-gradient(1000px 500px at 92% 12%, #ede7f6 0%, transparent 60%),
    radial-gradient(900px 500px at 20% 90%, #fff3e0 0%, transparent 55%);
}
.block-container{ padding-top:1.1rem; }
[data-testid="stForm"]{
  background:var(--card);
  border:1px solid #e2e8f0;
  border-radius:16px;
  padding:18px 20px;
  box-shadow:0 8px 24px rgba(2,6,23,.06);
}
[data-testid="stWidgetLabel"] p{ text-align:right; margin-bottom:.25rem; color:var(--muted); }
[data-testid="stWidgetLabel"] p::after{ content: " :"; }
input, textarea, select{ direction:rtl; text-align:right; }
</style>
""", unsafe_allow_html=True)

# =========================
# נתיבים/סודות + התמדה ארוכת טווח
# =========================
DATA_DIR   = Path("data")
BACKUP_DIR = DATA_DIR / "backups"
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

CSV_FILE      = DATA_DIR / "שאלון_שיבוץ.csv"
CSV_LOG_FILE  = DATA_DIR / "שאלון_שיבוץ_log.csv"
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "rawan_0304")

try:
    is_admin_mode = st.query_params.get("admin", ["0"])[0] == "1"
except Exception:
    is_admin_mode = st.experimental_get_query_params().get("admin", ["0"])[0] == "1"

# =========================
# פונקציות עזר
# =========================
def load_csv_safely(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    attempts = [
        dict(encoding="utf-8-sig"),
        dict(encoding="utf-8"),
        dict(encoding="utf-8-sig", engine="python", on_bad_lines="skip"),
        dict(encoding="utf-8", engine="python", on_bad_lines="skip"),
        dict(encoding="latin-1", engine="python", on_bad_lines="skip"),
    ]
    for kw in attempts:
        try:
            df = pd.read_csv(path, **kw)
            df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
            return df
        except Exception:
            continue
    return pd.DataFrame()

def save_master_row(row: dict) -> None:
    """שמירה מצטברת של שורה חדשה ל־CSV הראשי + גיבוי מתוארך."""
    row_df = pd.DataFrame([row])
    file_exists = CSV_FILE.exists()
    row_df.to_csv(
        CSV_FILE,
        mode="a",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\",
        lineterminator="\n",
    )
    try:
        df_all = load_csv_safely(CSV_FILE)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"שאלון_שיבוץ_{ts}.csv"
        df_all.to_csv(
            backup_path,
            index=False,
            encoding="utf-8-sig",
            quoting=csv.QUOTE_MINIMAL,
            escapechar="\\",
            lineterminator="\n",
        )
    except Exception as e:
        print("⚠ שגיאה בגיבוי:", e)

def append_to_log(row_df: pd.DataFrame) -> None:
    file_exists = CSV_LOG_FILE.exists()
    row_df.to_csv(
        CSV_LOG_FILE,
        mode="a",
        header=not file_exists,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\",
        lineterminator="\n",
    )

def df_to_excel_bytes(df: pd.DataFrame, sheet: str = "Sheet1") -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name=sheet, index=False)
        ws = w.sheets[sheet]
        for i, col in enumerate(df.columns):
            width = 12
            if not df.empty:
                width = min(60, max(12, int(df[col].astype(str).map(len).max()) + 4))
            ws.set_column(i, i, width)
    bio.seek(0)
    return bio.read()

def valid_email(v: str) -> bool:  return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", v.strip()))
def valid_phone(v: str) -> bool:  return bool(re.match(r"^0\d{1,2}-?\d{6,7}$", v.strip()))
def valid_id(v: str) -> bool:     return bool(re.match(r"^\d{8,9}$", v.strip()))

def show_errors(errors: list[str]):
    if not errors: return
    st.markdown("### :red[נמצאו שגיאות:]")
    for e in errors:
        st.markdown(f"- :red[{e}]")

# =========================
# מצב מנהל
# =========================
if is_admin_mode:
    st.title("🔑 גישת מנהל – צפייה והורדות")
    pwd = st.text_input("סיסמת מנהל", type="password", key="admin_pwd_input")
    if pwd == ADMIN_PASSWORD:
        st.success("התחברת בהצלחה ✅")

        df_master = load_csv_safely(CSV_FILE)
        df_log    = load_csv_safely(CSV_LOG_FILE)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📦 קובץ ראשי")
            st.write(f"סה\"כ רשומות: **{len(df_master)}**")
        with col2:
            st.subheader("🧾 קובץ יומן")
            st.write(f"סה\"כ רשומות ביומן: **{len(df_log)}**")

        if not df_master.empty:
            st.dataframe(df_master, use_container_width=True)
            st.download_button(
                "📊 הורד Excel – קובץ ראשי",
                data=df_to_excel_bytes(df_master, sheet="Master"),
                file_name="שאלון_שיבוץ_master.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("⚠ עדיין אין נתונים.")

        if not df_log.empty:
            st.dataframe(df_log, use_container_width=True)
            st.download_button(
                "📊 הורד Excel – יומן",
                data=df_to_excel_bytes(df_log, sheet="Log"),
                file_name="שאלון_שיבוץ_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        if pwd:
            st.error("סיסמה שגויה")
    st.stop()

# =========================
# רשימת שירותים לדירוג — 3 בלבד
# =========================
SITES = [
    "כפר הילדים חורפיש",
    "אנוש כרמיאל",
    "הפוך על הפוך צפת",
    "שירות מבחן לנוער עכו",
    "כלא חרמון",
    "בית חולים זיו",
    "שירותי רווחה קריית שמונה",
    "מרכז יום לגיל השלישי",
    "מועדונית נוער בצפת",
    "מרפאת בריאות הנפש צפת",
]
RANK_COUNT = 3  # במקום 10 – רק 3

# =========================
# טופס
# =========================
st.title("📋 שאלון שיבוץ סטודנטים – שנת הכשרה תשפ״ו")
st.caption("מלאו את כל הסעיפים. השדות המסומנים ב-* חובה.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "פרטים אישיים", "העדפת שיבוץ", "נתונים אקדמיים",
    "התאמות", "מוטיבציה", "סיכום ושליחה"
])

# --- סעיף 1 ---
with tab1:
    st.subheader("פרטים אישיים")
    first_name = st.text_input("שם פרטי *")
    last_name  = st.text_input("שם משפחה *")
    nat_id     = st.text_input("תעודת זהות *")
    gender = st.radio("מין *", ["זכר","נקבה"], horizontal=True)
    social_affil = st.selectbox("שיוך חברתי *", ["יהודי/ה","מוסלמי/ת","נוצרי/ה","דרוזי/ת"])
    phone   = st.text_input("מספר טלפון נייד * (050-1234567)")
    address = st.text_input("כתובת מלאה *")
    email   = st.text_input("כתובת דוא״ל *")
    study_year = st.selectbox("שנת לימודים *", [
        "תואר ראשון - שנה א'", "תואר ראשון - שנה ב'", "תואר ראשון - שנה ג'",
        "הסבה א'", "הסבה ב'", "אחר..."
    ])
    study_year_other = st.text_input("פרט/י *") if study_year == "אחר..." else ""
    track = st.text_input("מסלול לימודים / תואר *")
    mobility = st.selectbox("ניידות *", [
        "אוכל להיעזר ברכב / ברשותי רכב",
        "אוכל להגיע בתחבורה ציבורית",
        "אחר..."
    ])
    mobility_other = st.text_input("פרט/י *") if mobility == "אחר..." else ""

# --- סעיף 2 ---
with tab2:
    st.subheader("העדפת שיבוץ")
    prev_training = st.selectbox("האם עברת הכשרה מעשית בעבר? *", ["כן","לא"])
    prev_place = prev_mentor = prev_partner = ""
    if prev_training == "כן":
        prev_place  = st.text_input("שם מקום ותחום *")
        prev_mentor = st.text_input("שם מדריך ומיקום *")
        prev_partner= st.text_input("שם בן/בת זוג להכשרה *")

    chosen_domains = st.multiselect("בחרו עד 3 תחומים *", ["קהילה","מוגבלות","זקנה","ילדים ונוער","בריאות הנפש","שיקום","משפחה","נשים","בריאות","אחר..."], max_selections=3)
    domains_other = st.text_input("פרט/י *") if "אחר..." in chosen_domains else ""
    top_domain = st.selectbox("תחום מוביל *", ["— בחר/י —"] + chosen_domains if chosen_domains else ["— בחר/י —"])

    st.markdown("**דרגו עד 3 מוסדות (1 = הכי רוצים).**")

    for i in range(1, RANK_COUNT + 1):
        st.session_state.setdefault(f"rank_{i}", "— בחר/י —")
        opts = ["— בחר/י —"] + [s for s in SITES]
        current = st.session_state.get(f"rank_{i}", "— בחר/י —")
        st.session_state[f"rank_{i}"] = st.selectbox(
            f"מדרגה {i} *",
            options=opts,
            index=opts.index(current) if current in opts else 0,
            key=f"rank_{i}_select"
        )

    special_request = st.text_area("בקשות מיוחדות (אפשר לכתוב 'אין') *", height=100)

# --- סעיף 3 ---
with tab3:
    avg_grade = st.number_input("ממוצע ציונים *", min_value=0.0, max_value=100.0, step=0.1)

# --- סעיף 4 ---
with tab4:
    adjustments = st.multiselect("סוגי התאמות *", ["אין","הריון","מגבלה רפואית","רגישות לבית חולים","אלרגיה חמורה","נכות","רקע משפחתי רגיש","אחר..."])
    adjustments_other = st.text_input("פרט/י *") if "אחר..." in adjustments else ""
    adjustments_details = st.text_area("פרט *", height=100)

# --- סעיף 5 ---
with tab5:
    likert = ["בכלל לא מסכים/ה","1","2","3","4","מסכים/ה מאוד"]
    m1 = st.radio("מוכנות להשקיע *", likert, horizontal=True)
    m2 = st.radio("חשיבות ההכשרה *", likert, horizontal=True)
    m3 = st.radio("מחויבות והתמדה *", likert, horizontal=True)

# --- סעיף 6 ---
with tab6:
    confirm = st.checkbox("מאשר/ת כי המידע נכון *")
    submitted = st.button("שליחה ✉️")

# =========================
# ולידציה + שמירה
# =========================
if submitted:
    errors = []
    if not first_name.strip(): errors.append("שם פרטי חסר")
    if not last_name.strip(): errors.append("שם משפחה חסר")
    if not valid_id(nat_id): errors.append("תעודת זהות לא תקינה")
    if not valid_phone(phone): errors.append("טלפון לא תקין")
    if not valid_email(email): errors.append("דוא״ל לא תקין")
    if not track.strip(): errors.append("חסר מסלול לימודים")
    if not special_request.strip(): errors.append("יש לכתוב בקשה מיוחדת (או 'אין')")
    if not confirm: errors.append("יש לאשר את ההצהרה")

    if errors:
        show_errors(errors)
    else:
        row = {
            "תאריך": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "שם פרטי": first_name.strip(),
            "שם משפחה": last_name.strip(),
            "תעודת זהות": nat_id.strip(),
            "מין": gender,
            "שיוך חברתי": social_affil,
            "טלפון": phone.strip(),
            "כתובת": address.strip(),
            "אימייל": email.strip(),
            "שנת לימודים": study_year if study_year != "אחר..." else study_year_other,
            "מסלול": track.strip(),
            "ניידות": mobility if mobility != "אחר..." else mobility_other,
            "הכשרה קודמת": prev_training,
            "מקום קודם": prev_place.strip(),
            "מדריך קודם": prev_mentor.strip(),
            "שותף קודם": prev_partner.strip(),
            "תחומים": "; ".join(chosen_domains),
            "תחום מוביל": top_domain,
            "בקשה מיוחדת": special_request.strip(),
            "ממוצע": avg_grade,
            "התאמות": "; ".join(adjustments),
            "התאמות אחרות": adjustments_other.strip(),
            "פירוט התאמות": adjustments_details.strip(),
            "מוטיבציה 1": m1,
            "מוטיבציה 2": m2,
            "מוטיבציה 3": m3,
        }
        for i in range(1, RANK_COUNT + 1):
            row[f"דירוג {i}"] = st.session_state.get(f"rank_{i}", "— בחר/י —")

        try:
            save_master_row(row)
            append_to_log(pd.DataFrame([row]))
            st.success("✅ הטופס נשלח בהצלחה!")
        except Exception as e:
            st.error(f"❌ שמירה נכשלה: {e}")
