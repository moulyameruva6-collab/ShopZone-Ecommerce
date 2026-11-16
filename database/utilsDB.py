
from database.connection import DatabaseConnection


class AuthQueries:

    # Get user data using email
    @staticmethod
    def getUserData(email: str):
        db_config = None
        cursor = None

        try:
            db_config = DatabaseConnection()
            cursor = db_config.cursor(dictionary=True)

            query = """
                SELECT * FROM users
                WHERE email = %s
            """

            cursor.execute(query, (email,))
            user = cursor.fetchone()

            if user:
                return True, user

            return False, "Email Not Exists"

        except Exception as e:
            return False, f"getUserData Error: {e}"

        finally:
            if cursor:
                cursor.close()

            if db_config:
                db_config.close()

    # Create user account
    @staticmethod
    def createUserAccount(
        name: str,
        email: str,
        password: str,
        phone: str
    ):
        db_config = None
        cursor = None

        try:
            db_config = DatabaseConnection()
            cursor = db_config.cursor()

            query = """
                INSERT INTO users
                (username, email, hashpassword, phone)
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (name, email, password, phone)
            )

            db_config.commit()

            return True, "Account created"

        except Exception as e:
            if db_config:
                db_config.rollback()

            return False, f"createUserAccount Error: {e}"

        finally:
            if cursor:
                cursor.close()

            if db_config:
                db_config.close()
