import sqlite3
conn = sqlite3.connect(':memory:')
conn.execute("CREATE TABLE test (val TEXT CHECK (val IN ('a','b')))")
try:
    conn.execute("INSERT INTO test VALUES ('c')")
    print("CHECK constraint NOT enforced")
except sqlite3.IntegrityError as e:
    print(f"CHECK constraint enforced: {e}")
conn.close()
