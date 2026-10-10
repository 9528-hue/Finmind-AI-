import sqlite3

db = sqlite3.connect("finmind.db")

db.execute("""
DELETE FROM alerts
WHERE transaction_id IN (
    SELECT id FROM transactions
    WHERE currency = 'USD'
)
""")

db.execute("""
DELETE FROM transactions
WHERE currency = 'USD'
""")

db.execute("""
DELETE FROM accounts
WHERE currency = 'USD'
""")

db.commit()
db.close()

print("Demo USD data removed successfully")