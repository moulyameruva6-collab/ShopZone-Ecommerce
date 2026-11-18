
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def DatabaseConnection():
    try:
        db_config = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            sslmode=os.getenv("DB_SSLMODE", "require")
        )

        return db_config

    except psycopg2.Error as e:
        print("Database Connection Error:", e)
        raise
