import sqlite3

conn = sqlite3.connect("quality.db")

result = conn.execute("PRAGMA integrity_check").fetchone()

print(result)

conn.close()