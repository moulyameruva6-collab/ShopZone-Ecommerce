
from database.connection import DatabaseConnection

db = DatabaseConnection()

if db.is_connected():
    print("Database Connected Successfully")

db.close()
