from database.connection import DatabaseConnection

db = DatabaseConnection()

if db.closed == 0:
    print("Database Connected Successfully")
else:
    print("Database Connection Failed")

db.close()