import mysql.connector as SQLC
import os
from dotenv import load_dotenv

load_dotenv()


def DatabaseConnection():
    try:
        db_config = SQLC.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )

        return db_config

    except SQLC.Error as e:
        raise Exception(f"Database connection failed: {e}")