
import os
import mysql.connector
import psycopg2
from dotenv import load_dotenv

load_dotenv()

mysql_db = None
postgres_db = None
mysql_cursor = None
postgres_cursor = None

try:
    # MySQL connection
    mysql_db = mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("MYSQL_PASSWORD"),
        database="ecommerce3"
    )

    # PostgreSQL connection
    postgres_db = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )

    mysql_cursor = mysql_db.cursor(dictionary=True)
    postgres_cursor = postgres_db.cursor()

    # Fetch MySQL products
    mysql_cursor.execute("""
        SELECT
            product_id,
            product_name,
            description,
            quantity,
            category,
            imgname,
            buyprice,
            saleprice,
            storedpath,
            is_active,
            created_at,
            updated_at
        FROM products
    """)

    products = mysql_cursor.fetchall()

    print("MySQL Products Found:", len(products))

    migrated = 0
    skipped = 0

    for product in products:

        # Check existing product ID
        postgres_cursor.execute("""
            SELECT product_id
            FROM products
            WHERE product_id = %s
        """, (product["product_id"],))

        if postgres_cursor.fetchone():
            print("Already Exists:", product["product_name"])
            skipped += 1
            continue

        storedpath = product["storedpath"]

        if storedpath:
            storedpath = storedpath.replace("\\", "/")

        # Insert product into PostgreSQL
        postgres_cursor.execute("""
            INSERT INTO products (
                product_id,
                product_name,
                description,
                quantity,
                category,
                imgname,
                buyprice,
                saleprice,
                storedpath,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """, (
            product["product_id"],
            product["product_name"],
            product["description"],
            product["quantity"],
            product["category"],
            product["imgname"],
            product["buyprice"],
            product["saleprice"],
            storedpath,
            bool(product["is_active"]),
            product["created_at"],
            product["updated_at"]
        ))

        migrated += 1
        print("Migrated:", product["product_name"])

    # Update identity sequence
    postgres_cursor.execute("""
        SELECT setval(
            pg_get_serial_sequence('products', 'product_id'),
            COALESCE((SELECT MAX(product_id) FROM products), 1),
            EXISTS (SELECT 1 FROM products)
        )
    """)

    postgres_db.commit()

    print("\nMigration Completed!")
    print("Migrated:", migrated)
    print("Skipped:", skipped)

except Exception as e:

    if postgres_db:
        postgres_db.rollback()

    print("Migration Error:", e)

finally:

    if mysql_cursor:
        mysql_cursor.close()

    if postgres_cursor:
        postgres_cursor.close()

    if mysql_db:
        mysql_db.close()

    if postgres_db:
        postgres_db.close()
