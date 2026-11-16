from database.connection import DatabaseConnection


class AdminQueries:

    # --------------------------------------------------
    # INSERT PRODUCT
    # --------------------------------------------------
    @staticmethod
    def insertProductRecord(product_data):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            query = """
                INSERT INTO products
                (product_name, description, category, saleprice,
                 quantity, imgname, storedpath)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """

            cursor.execute(query, product_data)
            db.commit()

            return True, "Product added successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("INSERT PRODUCT ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET ALL PRODUCTS / SINGLE PRODUCT
    # --------------------------------------------------
    @staticmethod
    def getAllProducts(
        product_name=None,
        product_id=None,
        category=None,
        page_no=1,
        per_page=7
    ):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            query = """
                SELECT *,
                    product_id AS productid,
                    product_name AS productname
                FROM products
                WHERE 1=1
            """

            values = []

            if product_name:
                query += " AND product_name LIKE %s"
                values.append(f"%{product_name}%")

            if category:
                query += " AND category=%s"
                values.append(category)

            if product_id:
                query += " AND product_id=%s"
                values.append(product_id)

                cursor.execute(query, tuple(values))
                return True, cursor.fetchone()

            page_no = max(int(page_no), 1)
            per_page = max(int(per_page), 1)

            offset = (page_no - 1) * per_page

            query += """
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """

            values.extend([per_page, offset])

            cursor.execute(query, tuple(values))

            return True, cursor.fetchall()

        except Exception as e:
            print("GET PRODUCTS ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET CATEGORIES
    # --------------------------------------------------
    @staticmethod
    def getAllCategories():
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            cursor.execute("""
                SELECT DISTINCT category
                FROM products
                WHERE category IS NOT NULL
                AND category != ''
                ORDER BY category
            """)

            return True, cursor.fetchall()

        except Exception as e:
            print("GET CATEGORIES ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # UPDATE PRODUCT
    # --------------------------------------------------
    @staticmethod
    def updateProductRecord(product_data):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            query = """
                UPDATE products
                SET product_name=%s,
                    description=%s,
                    category=%s,
                    saleprice=%s,
                    quantity=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE product_id=%s
            """

            cursor.execute(query, product_data)
            db.commit()

            return cursor.rowcount > 0, "Product updated successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("UPDATE PRODUCT ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # DELETE PRODUCT (SOFT DELETE)
    # --------------------------------------------------
    @staticmethod
    def deleteProduct(product_id):
        return AdminQueries.deactivateProduct(product_id)

    # --------------------------------------------------
    # DEACTIVATE PRODUCT
    # --------------------------------------------------
    @staticmethod
    def deactivateProduct(product_id):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            cursor.execute("""
                UPDATE products
                SET is_active=0
                WHERE product_id=%s
            """, (product_id,))

            db.commit()

            return cursor.rowcount > 0, "Product deactivated successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("DEACTIVATE PRODUCT ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # ACTIVATE PRODUCT
    # --------------------------------------------------
    @staticmethod
    def activateProduct(product_id):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            cursor.execute("""
                UPDATE products
                SET is_active=1
                WHERE product_id=%s
            """, (product_id,))

            db.commit()

            return cursor.rowcount > 0, "Product activated successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("ACTIVATE PRODUCT ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # CHANGE PRODUCT STATUS
    # --------------------------------------------------
    @staticmethod
    def chengeProductActivateStatus(product_id, status):
        if status:
            return AdminQueries.activateProduct(product_id)

        return AdminQueries.deactivateProduct(product_id)

    # --------------------------------------------------
    # GET FILTERED PRODUCTS WITH PAGINATION
    # --------------------------------------------------
    @staticmethod
    def getProducts(
        search="",
        category="",
        status="",
        stock="",
        min_price=None,
        max_price=None,
        page=1,
        per_page=7
    ):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            conditions = ["1=1"]
            values = []

            if search:
                conditions.append(
                    "(product_name LIKE %s OR category LIKE %s)"
                )

                values.extend([
                    f"%{search}%",
                    f"%{search}%"
                ])

            if category:
                conditions.append("category=%s")
                values.append(category)

            if status == "active":
                conditions.append("is_active=1")

            elif status == "inactive":
                conditions.append("is_active=0")

            if stock == "available":
                conditions.append("quantity > 5")

            elif stock == "low":
                conditions.append("quantity > 0 AND quantity <= 5")

            elif stock == "out":
                conditions.append("quantity=0")

            if min_price is not None:
                conditions.append("saleprice >= %s")
                values.append(min_price)

            if max_price is not None:
                conditions.append("saleprice <= %s")
                values.append(max_price)

            where_clause = " AND ".join(conditions)

            count_query = f"""
                SELECT COUNT(*) AS total
                FROM products
                WHERE {where_clause}
            """

            cursor.execute(count_query, tuple(values))
            total = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT DISTINCT category
                FROM products
                WHERE category IS NOT NULL
                AND category != ''
                ORDER BY category
            """)

            categories = [
                row["category"]
                for row in cursor.fetchall()
            ]

            page = max(int(page), 1)
            per_page = max(int(per_page), 1)

            offset = (page - 1) * per_page

            query = f"""
                SELECT *,
                    product_id AS productid,
                    product_name AS productname
                FROM products
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """

            query_values = values + [per_page, offset]

            cursor.execute(query, tuple(query_values))

            products = cursor.fetchall()

            return {
                "products": products,
                "total": total,
                "categories": categories
            }

        except Exception as e:
            print("GET FILTERED PRODUCTS ERROR:", e)

            return {
                "products": [],
                "total": 0,
                "categories": []
            }

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET ALL USERS
    # --------------------------------------------------
    @staticmethod
    def getUsers():
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT *,
                    user_id AS userid,
                    username AS name
                FROM users
                ORDER BY created_at DESC
            """)

            return True, cursor.fetchall()

        except Exception as e:
            print("GET USERS ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET USER BY ID
    # --------------------------------------------------
    @staticmethod
    def getUserById(userid):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT *,
                    user_id AS userid,
                    username AS name
                FROM users
                WHERE user_id=%s
            """, (userid,))

            return cursor.fetchone()

        except Exception as e:
            print("GET USER ERROR:", e)
            return None

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET USER DETAILS
    # --------------------------------------------------
    @staticmethod
    def getUserDetails(userid):
        return AdminQueries.getUserById(userid)

    # --------------------------------------------------
    # UPDATE USER
    # --------------------------------------------------
    @staticmethod
    def updateUser(user_data):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            query = """
                UPDATE users
                SET username=%s,
                    email=%s,
                    phone=%s,
                    role=%s,
                    is_active=%s
                WHERE user_id=%s
            """

            cursor.execute(query, user_data)
            db.commit()

            return cursor.rowcount > 0, "User updated successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("UPDATE USER ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET ALL ORDERS
    # --------------------------------------------------
    @staticmethod
    def getOrders(search=None, status=None):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            query = """
                SELECT
                    o.order_id AS id,
                    o.order_id AS order_id,
                    o.order_id AS orderid,
                    o.user_id AS userid,
                    u.username AS customer_name,
                    u.email AS customer_email,
                    o.total AS total,
                    o.total AS total_amount,
                    o.status,
                    o.address,
                    o.created_at,
                    p.method AS payment_method,
                    p.status AS payment_status,
                    p.amount AS payment_amount,
                    p.razorpay_order_id,
                    p.razorpay_payment_id,
                    COALESCE(od.item_count, 0) AS item_count
                FROM orders o
                JOIN users u ON u.user_id=o.user_id
                LEFT JOIN payment p ON p.order_id=o.order_id
                LEFT JOIN (
                    SELECT order_id, COUNT(*) AS item_count
                    FROM orderdetails
                    GROUP BY order_id
                ) od ON od.order_id=o.order_id
                WHERE 1=1
            """

            values = []

            if search:
                query += """
                    AND (
                        CAST(o.order_id AS CHAR) LIKE %s
                        OR u.username LIKE %s
                        OR u.email LIKE %s
                    )
                """

                values.extend([
                    f"%{search}%",
                    f"%{search}%",
                    f"%{search}%"
                ])

            if status:
                query += " AND LOWER(o.status)=%s"
                values.append(status.lower())

            query += " ORDER BY o.created_at DESC"

            cursor.execute(query, tuple(values))

            return True, cursor.fetchall()

        except Exception as e:
            print("GET ORDERS ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET ORDER BY ID
    # --------------------------------------------------
    @staticmethod
    def getOrderById(order_id):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            query = """
                SELECT
                    o.order_id AS id,
                    o.order_id AS order_id,
                    o.order_id AS orderid,
                    o.user_id AS userid,
                    o.status,
                    o.address,
                    o.total,
                    o.total AS total_amount,
                    o.created_at,
                    u.username AS customer_name,
                    u.email AS customer_email,
                    u.phone,
                    p.method AS payment_method,
                    p.status AS payment_status,
                    p.amount AS payment_amount,
                    p.razorpay_order_id,
                    p.razorpay_payment_id
                FROM orders o
                LEFT JOIN users u ON u.user_id=o.user_id
                LEFT JOIN payment p ON p.order_id=o.order_id
                WHERE o.order_id=%s
            """

            cursor.execute(query, (order_id,))

            return cursor.fetchone()

        except Exception as e:
            print("GET ORDER BY ID ERROR:", e)
            return None

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET ORDER ITEMS
    # --------------------------------------------------
    @staticmethod
    def getOrderItems(order_id):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(dictionary=True)

            query = """
                SELECT
                    od.order_id AS orderid,
                    od.product_id AS productid,
                    od.quantity,
                    od.price,
                    od.subtotal,
                    p.product_name AS productname,
                    p.product_name AS product_name,
                    p.category,
                    p.imgname,
                    p.storedpath,
                    p.storedpath AS image
                FROM orderdetails od
                LEFT JOIN products p
                    ON p.product_id=od.product_id
                WHERE od.order_id=%s
            """

            cursor.execute(query, (order_id,))

            return cursor.fetchall()

        except Exception as e:
            print("GET ORDER ITEMS ERROR:", e)
            return []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # --------------------------------------------------
    # GET COMPLETE ORDER DETAILS
    # --------------------------------------------------
    @staticmethod
    def getOrderDetails(order_id):
        order = AdminQueries.getOrderById(order_id)

        if not order:
            return None

        items = AdminQueries.getOrderItems(order_id)

        subtotal = sum(
            float(item.get("subtotal") or 0)
            for item in items
        )

        total = float(order.get("total") or 0)

        order["items"] = items
        order["subtotal"] = subtotal
        order["shipping"] = max(total - subtotal, 0)
        order["total_amount"] = total

        return order

    # --------------------------------------------------
    # UPDATE ORDER STATUS
    # --------------------------------------------------
    @staticmethod
    def updateOrderStatus(order_id, status):
        db = cursor = None

        try:
            db = DatabaseConnection()
            db.start_transaction()
            cursor = db.cursor(dictionary=True)

            cursor.execute("""
                SELECT status
                FROM orders
                WHERE order_id=%s
                FOR UPDATE
            """, (order_id,))

            order = cursor.fetchone()

            if not order:
                db.rollback()
                return False, "Order not found"

            old_status = str(order["status"]).lower()
            new_status = str(status).lower()

            allowed_statuses = [
                "pending",
                "shipped",
                "delivered",
                "cancelled"
            ]

            if new_status not in allowed_statuses:
                db.rollback()
                return False, "Invalid order status"

            if old_status == "cancelled":
                db.rollback()
                return False, "Order is already cancelled"

            if new_status == "cancelled":
                cursor.execute("""
                    SELECT product_id, quantity
                    FROM orderdetails
                    WHERE order_id=%s
                """, (order_id,))

                items = cursor.fetchall()

                for item in items:
                    cursor.execute("""
                        UPDATE products
                        SET quantity=quantity+%s
                        WHERE product_id=%s
                    """, (
                        item["quantity"],
                        item["product_id"]
                    ))

                cursor.execute("""
                    UPDATE payment
                    SET status='failed'
                    WHERE order_id=%s
                    AND LOWER(status)='pending'
                """, (order_id,))

            cursor.execute("""
                UPDATE orders
                SET status=%s
                WHERE order_id=%s
            """, (new_status, order_id))

            db.commit()

            return True, "Order status updated successfully"

        except Exception as e:
            if db:
                db.rollback()

            print("UPDATE ORDER STATUS ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()