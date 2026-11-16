
from database.connection import DatabaseConnection


def createTables():
    db_config = None
    cursor = None

    try:
        db_config = DatabaseConnection()
        cursor = db_config.cursor()

        users_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            hashpassword VARCHAR(255) NOT NULL,
            role ENUM('admin','user') DEFAULT 'user',
            phone VARCHAR(15),
            dateofbirth DATE,
            profilename VARCHAR(255),
            profilepath VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
        """

        products_table_query = """
        CREATE TABLE IF NOT EXISTS products (
            product_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(150) NOT NULL,
            description TEXT,
            quantity INT UNSIGNED DEFAULT 0,
            category VARCHAR(100),
            imgname VARCHAR(255),
            buyprice DECIMAL(15,2) DEFAULT 0.00,
            saleprice DECIMAL(15,2) DEFAULT 0.00,
            storedpath VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        )
        """

        orders_table_query = """
        CREATE TABLE IF NOT EXISTS orders (
            order_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            status ENUM(
                'shipped','delivered','cancelled','pending'
            ) DEFAULT 'pending',
            address VARCHAR(255),
            total DECIMAL(15,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """

        orderdetails_table_query = """
        CREATE TABLE IF NOT EXISTS orderdetails (
            order_detail_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            order_id BIGINT,
            product_id BIGINT,
            quantity INT UNSIGNED DEFAULT 1,
            price DECIMAL(15,2) DEFAULT 0.00,
            subtotal DECIMAL(20,2)
                GENERATED ALWAYS AS (quantity * price) STORED,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        """

        payment_table_query = """
        CREATE TABLE IF NOT EXISTS payment (
            payment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            order_id BIGINT,
            method ENUM('cash','upi','netbanking'),
            amount DECIMAL(20,2) DEFAULT 0.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(100),
            razorpay_id VARCHAR(100),
            razorpay_order_id VARCHAR(255),
            razorpay_payment_id VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
        """

        cart_table_query = """
        CREATE TABLE IF NOT EXISTS cart (
            cartid BIGINT AUTO_INCREMENT PRIMARY KEY,
            userid BIGINT,
            productid BIGINT,
            quantity INT UNSIGNED DEFAULT 1,
            FOREIGN KEY (userid) REFERENCES users(user_id),
            FOREIGN KEY (productid) REFERENCES products(product_id)
        )
        """

        tables = [
            users_table_query,
            products_table_query,
            orders_table_query,
            orderdetails_table_query,
            payment_table_query,
            cart_table_query
        ]

        for query in tables:
            cursor.execute(query)

        db_config.commit()

        return "Tables Created Successfully"

    except Exception as e:
        if db_config and db_config.is_connected():
            db_config.rollback()

        return f"Database Error: {e}"

    finally:
        if cursor:
            cursor.close()

        if db_config and db_config.is_connected():
            db_config.close()
