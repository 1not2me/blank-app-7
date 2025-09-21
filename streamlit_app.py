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

# ====== עיצוב — לפי ה-CSS שביקשת ======
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

CSV_FILE      = DATA_DIR / "שאלון_שיבוץ.csv"         # קובץ ראשי (מצטבר, לעולם לא מתאפס)
CSV_LOG_FILE  = DATA_DIR / "שאלון_שיבוץ_log.csv"     # יומן הוספות (Append-Only)
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "rawan_0304")  # מומלץ לשים ב-secrets

# תמיכה בפרמטר admin=1 ב-URL
try:
    is_admin_mode = st.query_params.get("admin", ["0"])[0] == "1"
except Exception:
    is_admin_mode = st.experimental_get_query_params().get("admin", ["0"])[0] == "1"

# =========================
# פונקציות עזר (קבצים/ולידציה/ייצוא)
# =========================
def load_csv_safely(path: Path) -> pd.DataFrame:
    """קריאה חסינה של CSV במספר קידודים, עם דילוג על שורות פגומות במקרה הצורך."""
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

def save_master_dataframe(df: pd.DataFrame) -> None:
    """
    שמירה אטומית של הקובץ הראשי + גיבוי מתוארך.
    לעולם לא מוחקים נתונים קיימים – תמיד מצרפים.
    """
    tmp = CSV_FILE.with_suffix(".tmp.csv")
    df.to_csv(
        tmp,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\",
        lineterminator="\n",
    )
    tmp.replace(CSV_FILE)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"שאלון_שיבוץ_{ts}.csv"
    df.to_csv(
        backup_path,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        escapechar="\\",
        lineterminator="\n",
    )

def append_to_log(row_df: pd.DataFrame) -> None:
    """יומן Append-Only — מוסיפים שורות בלבד."""
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
    """המרת DataFrame ל-Excel בזיכרון עם התאמת רוחב עמודות."""
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
def valid_phone(v: str) -> bool:  return bool(re.match(r"^0\d{1,2}-?\d{6,7}$", v.strip()))   # 050-1234567 / 04-8123456
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
    st.title("🔑 גישת מנהל – צפייה והורדות (מאסטר + יומן)")
    pwd = st.text_input("סיסמת מנהל", type="password", key="admin_pwd_input")
    if pwd == ADMIN_PASSWORD:
        st.success("התחברת בהצלחה ✅")

        df_master = load_csv_safely(CSV_FILE)
        df_log    = load_csv_safely(CSV_LOG_FILE)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📦 קובץ ראשי (מצטבר, לעולם לא נמחק)")
            st.write(f"סה\"כ רשומות: **{len(df_master)}**")
        with col2:
            st.subheader("🧾 קובץ יומן (Append-Only)")
            st.write(f"סה\"כ רשומות ביומן: **{len(df_log)}**")

        st.markdown("### הקובץ הראשי")
        if not df_master.empty:
            st.dataframe(df_master, use_container_width=True)
            st.download_button(
                "📊 הורד Excel – קובץ ראשי",
                data=df_to_excel_bytes(df_master, sheet="Master"),
                file_name="שאלון_שיבוץ_master.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_master_xlsx"
            )
        else:
            st.info("⚠ עדיין אין נתונים בקובץ הראשי.")

        st.markdown("---")
        st.markdown("### קובץ היומן (Append-Only)")
        if not df_log.empty:
            st.dataframe(df_log, use_container_width=True)
            st.download_button(
                "📊 הורד Excel – יומן הוספות",
                data=df_to_excel_bytes(df_log, sheet="Log"),
                file_name="שאלון_שיבוץ_log.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_log_xlsx"
            )
        else:
            st.info("⚠ עדיין אין נתונים ביומן.")

        with st.expander("🗂️ גיבויים (קריאה בלבד)"):
            backups = sorted(BACKUP_DIR.glob("שאלון_שיבוץ_*.csv"))
            if backups:
                st.write(f"נמצאו {len(backups)} גיבויים בתיקייה: `{BACKUP_DIR}`")
                st.write("\n".join(b.name for b in backups[-12:]))
            else:
                st.caption("אין עדיין גיבויים.")
    else:
        if pwd:
            st.error("סיסמה שגויה")
    st.stop()

# =========================
# רשימת שירותים לדירוג — 3 פריטים (עודכן)
# =========================
SITES = [
    "כפר הילדים חורפיש",
    "אנוש כרמיאל",
    "הפוך על הפוך צפת",
]
RANK_COUNT = len(SITES)  # 3

# =========================
# טפסים – (המשך הקוד כמו אצלך, ללא שינוי חוץ מ־RANK_COUNT ותיקון הטקסט)
# =========================
# --- (שאר הקוד נשאר זהה, כולל כל הסעיפים, ולבסוף...)

# =========================
# ולידציה + שמירה
# =========================
if submitted:
    errors = []

    # ... סעיפים קודמים ...

    if prev_training in ["כן","אחר..."]:
        if not prev_place.strip():  errors.append("סעיף 2: יש למלא מקום/תחום אם הייתה הכשרה קודמת.")
        if not prev_mentor.strip(): errors.append("סעיף 2: יש למלא שם מדריך ומיקום.")
        if not prev_partner.strip(): errors.append("סעיף 2: יש למלא בן/בת זוג להתמחות.")  # ← תוקן כאן

    # ... המשך שמירה כמו בקוד שלך ...
