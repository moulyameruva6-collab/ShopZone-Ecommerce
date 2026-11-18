
from database.connection import DatabaseConnection
from psycopg2.extras import RealDictCursor


class UserQueries:

    # ADD CART ITEM
    @staticmethod
    def addCartItem(product_id, userid, quantity):
        db = cursor = None

        try:
            quantity = int(quantity)

            if quantity <= 0:
                return False, "Invalid quantity"

            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT product_id, quantity
                FROM products
                WHERE product_id=%s AND is_active=TRUE
            """, (product_id,))

            product = cursor.fetchone()

            if not product:
                return False, "Product not available"

            cursor.execute("""
                SELECT cartid, quantity
                FROM cart
                WHERE userid=%s AND productid=%s
            """, (userid, product_id))

            cart_item = cursor.fetchone()

            new_quantity = quantity

            if cart_item:
                new_quantity += cart_item["quantity"]

            if new_quantity > product["quantity"]:
                return False, "Insufficient stock"

            if cart_item:
                cursor.execute("""
                    UPDATE cart
                    SET quantity=%s
                    WHERE cartid=%s AND userid=%s
                """, (new_quantity, cart_item["cartid"], userid))
            else:
                cursor.execute("""
                    INSERT INTO cart(userid, productid, quantity)
                    VALUES(%s, %s, %s)
                """, (userid, product_id, quantity))

            db.commit()
            return True, "Product added to cart"

        except Exception as e:
            if db:
                db.rollback()
            print("ADD CART ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # GET CART ITEMS
    @staticmethod
    def getCartItems(userid):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    c.cartid,
                    c.userid,
                    c.productid,
                    c.quantity,
                    p.product_name AS productname,
                    p.product_name,
                    p.category,
                    p.saleprice,
                    p.storedpath,
                    p.imgname,
                    (c.quantity * p.saleprice) AS subtotal
                FROM cart c
                JOIN products p
                    ON p.product_id=c.productid
                WHERE c.userid=%s
                ORDER BY c.cartid DESC
            """, (userid,))

            return True, cursor.fetchall()

        except Exception as e:
            print("GET CART ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # UPDATE CART QUANTITY
    @staticmethod
    def updateCartItemQuantity(cartid, quantity, userid=None):
        db = cursor = None

        try:
            quantity = int(quantity)

            if quantity <= 0:
                return False, "Quantity must be greater than zero"

            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    c.cartid,
                    c.quantity,
                    p.quantity AS stock
                FROM cart c
                JOIN products p
                    ON p.product_id=c.productid
                WHERE c.cartid=%s
            """

            values = [cartid]

            if userid is not None:
                query += " AND c.userid=%s"
                values.append(userid)

            cursor.execute(query, tuple(values))
            item = cursor.fetchone()

            if not item:
                return False, "Cart item not found"

            if quantity > item["stock"]:
                return False, "Insufficient stock"

            cursor.execute("""
                UPDATE cart
                SET quantity=%s
                WHERE cartid=%s
            """, (quantity, cartid))

            db.commit()
            return True, "Cart updated successfully"

        except Exception as e:
            if db:
                db.rollback()
            print("UPDATE CART ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # DELETE CART ITEM
    @staticmethod
    def deleteCartItem(cartid, userid=None):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            query = "DELETE FROM cart WHERE cartid=%s"
            values = [cartid]

            if userid is not None:
                query += " AND userid=%s"
                values.append(userid)

            cursor.execute(query, tuple(values))
            deleted = cursor.rowcount

            db.commit()

            return deleted > 0, "Cart item removed"

        except Exception as e:
            if db:
                db.rollback()
            print("DELETE CART ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # GET USER
    @staticmethod
    def getUser(userid):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT *,
                    user_id AS userid,
                    username AS name
                FROM users
                WHERE user_id=%s
            """, (userid,))

            user = cursor.fetchone()
            return (True, user) if user else (False, None)

        except Exception as e:
            print("GET USER ERROR:", e)
            return False, None

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # GET USER PROFILE
    @staticmethod
    def getUserProfile(userid):
        return UserQueries.getUser(userid)

    # UPDATE USER PROFILE
    @staticmethod
    def updateUserProfile(userid, username, phone, dateofbirth):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor()

            cursor.execute("""
                UPDATE users
                SET username=%s,
                    phone=%s,
                    dateofbirth=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE user_id=%s
            """, (
                username,
                phone,
                dateofbirth or None,
                userid
            ))

            db.commit()
            return cursor.rowcount >= 0, "Profile updated successfully"

        except Exception as e:
            if db:
                db.rollback()
            print("UPDATE PROFILE ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # CREATE ORDER
    @staticmethod
    def createOrder(
        userid,
        address,
        payment_method,
        razorpay_order_id=None,
        razorpay_payment_id=None
    ):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    c.cartid,
                    c.productid,
                    c.quantity,
                    p.product_name,
                    p.saleprice,
                    p.quantity AS stock,
                    p.is_active
                FROM cart c
                JOIN products p
                    ON p.product_id=c.productid
                WHERE c.userid=%s
                FOR UPDATE OF c, p
            """, (userid,))

            cart_items = cursor.fetchall()

            if not cart_items:
                db.rollback()
                return False, "Your cart is empty"

            subtotal = 0.0

            for item in cart_items:
                if not item["is_active"]:
                    db.rollback()
                    return False, f'{item["product_name"]} is not available'

                if item["quantity"] > item["stock"]:
                    db.rollback()
                    return False, f'Insufficient stock for {item["product_name"]}'

                subtotal += float(item["saleprice"]) * item["quantity"]

            shipping = round(subtotal * 0.01, 2)
            total = round(subtotal + shipping, 2)

            cursor.execute("""
                INSERT INTO orders
                (user_id, status, address, total)
                VALUES(%s, %s, %s, %s)
                RETURNING order_id
            """, (userid, "pending", address, total))

            orderid = cursor.fetchone()["order_id"]

            for item in cart_items:
                cursor.execute("""
                    INSERT INTO orderdetails
                    (order_id, product_id, quantity, price)
                    VALUES(%s, %s, %s, %s)
                """, (
                    orderid,
                    item["productid"],
                    item["quantity"],
                    item["saleprice"]
                ))

                cursor.execute("""
                    UPDATE products
                    SET quantity=quantity-%s
                    WHERE product_id=%s
                    AND quantity >= %s
                """, (
                    item["quantity"],
                    item["productid"],
                    item["quantity"]
                ))

                if cursor.rowcount != 1:
                    raise Exception("Stock update failed")

            cursor.execute("""
                INSERT INTO payment
                (
                    user_id,
                    order_id,
                    method,
                    amount,
                    status,
                    razorpay_order_id,
                    razorpay_payment_id
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s)
            """, (
                userid,
                orderid,
                payment_method,
                total,
                "pending",
                razorpay_order_id,
                razorpay_payment_id
            ))

            cursor.execute("""
                DELETE FROM cart
                WHERE userid=%s
            """, (userid,))

            db.commit()

            return True, {
                "order_id": orderid,
                "amount": total
            }

        except Exception as e:
            if db:
                db.rollback()
            print("CREATE ORDER ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # GET USER ORDERS
    @staticmethod
    def getOrders(userid):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    o.order_id AS id,
                    o.order_id AS orderid,
                    o.order_id AS order_id,
                    o.status,
                    o.total AS total_amount,
                    o.address,
                    o.created_at,

                    p.payment_id AS payment_id,
                    p.method AS payment_method,
                    p.status AS payment_status,
                    p.amount AS payment_amount,
                    p.razorpay_payment_id AS payment_id_reference,

                    COALESCE(
                        (
                            SELECT SUM(od.quantity)
                            FROM orderdetails od
                            WHERE od.order_id=o.order_id
                        ), 0
                    ) AS item_count

                FROM orders o

                LEFT JOIN payment p
                    ON p.order_id=o.order_id
                    AND p.user_id=o.user_id

                WHERE o.user_id=%s

                ORDER BY o.created_at DESC
            """, (userid,))

            return True, cursor.fetchall()

        except Exception as e:
            print("GET USER ORDERS ERROR:", e)
            return False, []

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # GET ORDER DETAILS
    @staticmethod
    def getOrderDetails(orderid, userid):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    o.order_id AS id,
                    o.order_id AS orderid,
                    o.order_id AS order_id,
                    o.user_id AS userid,
                    o.status,
                    o.address,
                    o.address AS delivery_address,
                    o.total,
                    o.total AS total_amount,
                    o.created_at,
                    u.username AS customer_name,
                    u.email AS customer_email,
                    u.phone,
                    p.method AS payment_method,
                    p.status AS payment_status,
                    p.amount AS payment_amount,
                    p.payment_id,
                    p.razorpay_order_id,
                    p.razorpay_payment_id
                FROM orders o
                LEFT JOIN users u
                    ON u.user_id=o.user_id
                LEFT JOIN payment p
                    ON p.order_id=o.order_id
                    AND p.user_id=o.user_id
                WHERE o.order_id=%s
                AND o.user_id=%s
            """, (orderid, userid))

            order = cursor.fetchone()

            if not order:
                return False, None

            cursor.execute("""
                SELECT
                    od.order_id AS orderid,
                    od.product_id AS productid,
                    od.quantity,
                    od.price,
                    od.subtotal,
                    p.product_name AS product_name,
                    p.product_name AS productname,
                    p.category,
                    p.imgname,
                    p.storedpath,
                    p.storedpath AS image
                FROM orderdetails od
                LEFT JOIN products p
                    ON p.product_id=od.product_id
                WHERE od.order_id=%s
            """, (orderid,))

            items = cursor.fetchall()

            subtotal = sum(
                float(item.get("subtotal") or 0)
                for item in items
            )

            total = float(order.get("total") or 0)

            order["items"] = items
            order["subtotal"] = subtotal
            order["shipping"] = max(total - subtotal, 0)
            order["total_amount"] = total

            return True, order

        except Exception as e:
            print("GET ORDER DETAILS ERROR:", e)
            return False, None

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # MARK RAZORPAY PAYMENT AS PAID
    @staticmethod
    def markPaid(userid, orderid, razorpay_order_id, payment_id):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT payment_id, status
                FROM payment
                WHERE user_id=%s
                AND order_id=%s
                AND razorpay_order_id=%s
                FOR UPDATE
            """, (userid, orderid, razorpay_order_id))

            payment = cursor.fetchone()

            if not payment:
                db.rollback()
                return False, "Payment record not found"

            if payment["status"] == "paid":
                db.commit()
                return True, "Payment already completed"

            cursor.execute("""
                UPDATE payment
                SET status='paid',
                    razorpay_payment_id=%s
                WHERE payment_id=%s
            """, (payment_id, payment["payment_id"]))

            cursor.execute("""
                UPDATE orders
                SET status='confirmed'
                WHERE order_id=%s AND user_id=%s
            """, (orderid, userid))

            db.commit()
            return True, "Payment successful"

        except Exception as e:
            if db:
                db.rollback()
            print("MARK PAID ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # FAIL PAYMENT
    @staticmethod
    def failPayment(userid, orderid, reason=None):
        db = cursor = None

        try:
            db = DatabaseConnection()
            cursor = db.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT status
                FROM orders
                WHERE order_id=%s
                AND user_id=%s
                FOR UPDATE
            """, (orderid, userid))

            order = cursor.fetchone()

            if not order:
                db.rollback()
                return False, "Order not found"

            cursor.execute("""
                SELECT status
                FROM payment
                WHERE order_id=%s
                AND user_id=%s
                FOR UPDATE
            """, (orderid, userid))

            payment = cursor.fetchone()

            if not payment:
                db.rollback()
                return False, "Payment not found"

            if payment["status"] == "paid":
                db.rollback()
                return False, "Payment already completed"

            if order["status"] == "cancelled":
                db.commit()
                return True, "Order already cancelled"

            cursor.execute("""
                SELECT product_id, quantity
                FROM orderdetails
                WHERE order_id=%s
            """, (orderid,))

            items = cursor.fetchall()

            for item in items:
                cursor.execute("""
                    UPDATE products
                    SET quantity=quantity+%s
                    WHERE product_id=%s
                """, (item["quantity"], item["product_id"]))

            cursor.execute("""
                UPDATE payment
                SET status='failed'
                WHERE order_id=%s AND user_id=%s
            """, (orderid, userid))

            cursor.execute("""
                UPDATE orders
                SET status='cancelled'
                WHERE order_id=%s AND user_id=%s
            """, (orderid, userid))

            db.commit()
            return True, "Payment failed and order cancelled"

        except Exception as e:
            if db:
                db.rollback()
            print("FAIL PAYMENT ERROR:", e)
            return False, str(e)

        finally:
            if cursor:
                cursor.close()
            if db:
                db.close()

    # CANCEL PENDING ORDER
    @staticmethod
    def cancelPendingOrder(userid, orderid):
        return UserQueries.failPayment(
            userid,
            orderid,
            "Order cancelled"
        )
