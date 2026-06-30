from flask import Flask, render_template, request, send_file
import pandas as pd
import sqlite3
import re
import os
from report_generator import generate_word_report

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)


# =========================
# DATABASE CONNECTION
# =========================

def get_db():
    conn = sqlite3.connect("quality.db")
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# INITIALIZE DATABASE
# =========================

def init_db():

    conn = sqlite3.connect("quality.db")

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT,
        group_name TEXT,
        declared_total INTEGER,
        actual_total INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER,
        agent_name TEXT,
        serial_number TEXT,
        usage REAL,
        commission REAL,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

# =========================
# SAVE REPORT
# =========================

def save_report_to_db(
    report_date,
    group_name,
    declared_total,
    actual_total,
    results
):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reports
        (report_date, group_name, declared_total, actual_total)
        VALUES (?,?,?,?)
    """, (
        report_date,
        group_name,
        declared_total,
        actual_total
    ))

    report_id = cur.lastrowid

    for row in results:

        cur.execute("""
            INSERT INTO report_details
            (report_id, agent_name, serial_number, usage, commission, status)
            VALUES (?,?,?,?,?,?)
        """, (
            report_id,
            row['Agent'],
            row['Serial Number'],
            row['Usage'],
            row['Commission'],
            row['Status']
        ))

    conn.commit()
    conn.close()

    return report_id


# =========================
# HISTORICAL CHECK
# =========================

def get_previous_usage(serial):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.report_date, r.group_name, d.agent_name
        FROM report_details d
        JOIN reports r ON r.id = d.report_id
        WHERE d.serial_number = ?
        ORDER BY r.id DESC
        LIMIT 1
    """, (serial,))

    row = cur.fetchone()
    conn.close()

    return row


# =========================
# BUILD SUMMARY HELPER
# Used by both process_report and export route
# =========================

def build_summary(results_df):

    summary = []

    if results_df.empty:
        return summary

    for agent in sorted(results_df['Agent'].dropna().unique()):

        agent_df = results_df[results_df['Agent'] == agent]

        # A row is QUALITY only if it contains "QUALITY" but NOT "NON QUALITY"
        quality_mask = (
            agent_df['Status'].str.contains("QUALITY") &
            ~agent_df['Status'].str.contains("NON QUALITY")
        )

        non_quality_mask = agent_df['Status'].str.contains("NON QUALITY")
        not_found_mask   = agent_df['Status'].str.contains("NOT FOUND")

        summary.append({
            'agent':       agent,
            'total':       len(agent_df),
            'quality':     len(agent_df[quality_mask]),
            'non_quality': len(agent_df[non_quality_mask]),
            'not_found':   len(agent_df[not_found_mask]),

            'non_quality_serials': [
                str(x)[-6:]
                for x in agent_df[non_quality_mask]['Serial Number']
            ],

            'not_found_serials': [
                str(x)[-6:]
                for x in agent_df[not_found_mask]['Serial Number']
            ]
        })

    return summary


# =========================
# PROCESS REPORT
# =========================

def process_report(df, report_text):

    df.columns = df.columns.str.strip()

    df['Sim Serial Number'] = df['Sim Serial Number'].astype(str).str.strip()
    df['Cumulative Usage'] = pd.to_numeric(df['Cumulative Usage'], errors='coerce')
    df['Cumulative Commission'] = pd.to_numeric(df['Cumulative Commission'], errors='coerce')

    # META DATA

    date_match = re.search(r'\d{2}/\d{2}/\d{4}', report_text)
    report_date = date_match.group() if date_match else "Unknown Date"

    group_match = re.search(r'\d{2}/\d{2}/\d{4}\s+report\s+(.+)', report_text, re.IGNORECASE)
    group_name = group_match.group(1).strip() if group_match else "Unknown Group"

    total_match = re.search(r'Total\s+lines\s+activated\s*-\s*(\d+)', report_text, re.IGNORECASE)
    declared_total = int(total_match.group(1)) if total_match else 0

    # PARSE REPORT

    records = []
    current_agent = None

    for line in report_text.splitlines():

        line = line.strip()
        if not line:
            continue

        agent_match = re.match(r'^([A-Za-z ]+)\s*-\s*\d+$', line)
        if agent_match:
            current_agent = agent_match.group(1).strip()
            continue

        if re.fullmatch(r'\d{20}', line):
            records.append({
                'Agent': current_agent,
                'Serial Number': line
            })

    actual_total = len(records)

    # DUPLICATE TRACKING
    seen = set()
    results = []

    for rec in records:

        serial = rec['Serial Number']

        duplicate_in_report = serial in seen
        seen.add(serial)

        match = df[df['Sim Serial Number'] == serial]
        prev = get_previous_usage(serial)

        if match.empty:

            status = "NOT FOUND"

            if duplicate_in_report:
                status = "DUPLICATE IN REPORT + NOT FOUND"

            results.append({
                'Agent': rec['Agent'],
                'Serial Number': serial,
                'Usage': '',
                'Commission': '',
                'Status': status
            })

            continue

        row = match.iloc[0]

        usage = row['Cumulative Usage']
        commission = row['Cumulative Commission']

        quality = (
            pd.notna(usage)
            and pd.notna(commission)
            and usage >= 50
            and commission >= 300
        )

        base_status = "QUALITY" if quality else "NON QUALITY"

        if prev:
            status = f"ALREADY USED + {base_status}"
        else:
            status = base_status

        if duplicate_in_report:
            status = f"DUPLICATE IN REPORT + {status}"

        results.append({
            'Agent': rec['Agent'],
            'Serial Number': serial,
            'Usage': usage,
            'Commission': commission,
            'Status': status
        })

    # SAVE DB
    report_id = save_report_to_db(
        report_date,
        group_name,
        declared_total,
        actual_total,
        results
    )

    # BUILD SUMMARY
    results_df = pd.DataFrame(results)
    summary = build_summary(results_df)

    # =========================
    # ACCURATE TOP-CARD COUNTS
    # Uses same logic as summary so reused/duplicate serials are handled correctly
    # =========================

    if not results_df.empty:
        quality_count = len(results_df[
            results_df['Status'].str.contains("QUALITY") &
            ~results_df['Status'].str.contains("NON QUALITY")
        ])
        non_quality_count = len(results_df[
            results_df['Status'].str.contains("NON QUALITY")
        ])
        not_found_count = len(results_df[
            results_df['Status'].str.contains("NOT FOUND")
        ])
    else:
        quality_count = non_quality_count = not_found_count = 0

    return (
        report_id,
        report_date,
        group_name,
        declared_total,
        actual_total,
        results,
        summary,
        quality_count,
        non_quality_count,
        not_found_count
    )


# =========================
# ROUTES
# =========================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():

    excel_file = request.files['excel_file']
    report_text = request.form['report_text']

    filepath = os.path.join(UPLOAD_FOLDER, excel_file.filename)
    excel_file.save(filepath)

    df = pd.read_excel(filepath)

    (
        report_id,
        report_date,
        group_name,
        declared_total,
        actual_total,
        results,
        summary,
        quality_count,
        non_quality_count,
        not_found_count
    ) = process_report(df, report_text)

    return render_template(
        'results.html',
        report_id=report_id,
        report_date=report_date,
        group_name=group_name,
        declared_total=declared_total,
        actual_total=actual_total,
        tally_match=(declared_total == actual_total),
        results=results,
        summary=summary,
        quality_count=quality_count,
        non_quality_count=non_quality_count,
        not_found_count=not_found_count
    )


# =========================
# FIXED EXPORT ROUTE
# =========================

@app.route('/export/<int:report_id>')
def export(report_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    report = cur.fetchone()

    cur.execute("SELECT * FROM report_details WHERE report_id=?", (report_id,))
    rows = cur.fetchall()

    conn.close()

    # Convert sqlite rows to dicts
    details = [
        {
            "Agent": r["agent_name"],
            "Serial Number": r["serial_number"],
            "Usage": r["usage"],
            "Commission": r["commission"],
            "Status": r["status"]
        }
        for r in rows
    ]

    # Rebuild summary from details so Word export has a populated summary section
    details_df = pd.DataFrame(details)
    export_summary = build_summary(details_df)

    file_path = generate_word_report(
        REPORT_FOLDER,
        report["report_date"],
        report["group_name"],
        report["declared_total"],
        report["actual_total"],
        (report["declared_total"] == report["actual_total"]),
        export_summary,
        details
    )

    return send_file(file_path, as_attachment=True)

@app.route('/all-dates')
def all_dates():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, report_date, group_name, created_at
        FROM reports
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return render_template("all_dates.html", rows=rows)

@app.route('/history', methods=['GET', 'POST'])
def history():

    conn = get_db()
    cur = conn.cursor()

    # Get all unique dates for dropdown
    cur.execute("""
        SELECT DISTINCT report_date
        FROM reports
        ORDER BY id DESC
    """)
    dates = [r['report_date'] for r in cur.fetchall()]

    selected_date = None
    reports = []
    details = []

    if request.method == 'POST':

        selected_date = request.form['report_date']

        cur.execute("""
            SELECT * FROM reports
            WHERE report_date = ?
            ORDER BY id DESC
        """, (selected_date,))

        reports = cur.fetchall()

        if reports:
            report_ids = [r['id'] for r in reports]
            placeholders = ",".join(["?"] * len(report_ids))

            cur.execute(f"""
                SELECT d.*, r.report_date, r.group_name
                FROM report_details d
                JOIN reports r ON r.id = d.report_id
                WHERE d.report_id IN ({placeholders})
            """, report_ids)

            details = cur.fetchall()

    conn.close()

    return render_template(
        "history.html",
        dates=dates,
        selected_date=selected_date,
        reports=reports,
        details=details
    )


init_db()

if __name__ == '__main__':
    app.run(debug=True)