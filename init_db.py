import sqlite3

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

print("Database created successfully.")