
import os
import uuid
import bcrypt
import razorpay
import logging

from decimal import Decimal
from functools import wraps
from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    session,
    flash,
    abort
)

from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash

# PostgreSQL database imports
from database.utilsDB import AuthQueries
from database.adminDB import AdminQueries
from database.userDB import UserQueries
from database.storage import upload_product_image

# ======================================================
# CONFIGURATION
# ======================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="[%(asctime)s] - %(levelname)s: %(message)s"
)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

app.config["UPLOAD_FOLDER"] = os.path.join(
    "static",
    "images",
    "products"
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)


# ======================================================
# COMMON FUNCTIONS
# ======================================================

def money(value):
    return Decimal(str(value or 0))


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def razorpay_client():

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay keys are missing in .env")

    return razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )


# ======================================================
# LOGIN DECORATORS
# ======================================================

def login_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "userid" not in session:
            flash("Please login first", "warning")
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return wrapper


def user_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "userid" not in session:
            flash("Please login first", "warning")
            return redirect(url_for("login"))

        if session.get("role") != "user":
            abort(403)

        return func(*args, **kwargs)

    return wrapper


def admin_required(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "userid" not in session:
            flash("Please login first", "warning")
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            abort(403)

        return func(*args, **kwargs)

    return wrapper


# ======================================================
# CART SUMMARY
# ======================================================

def cart_summary(userid):

    status, cart_items = UserQueries.getCartItems(userid)

    if not status:
        return [], 0, 0, 0

    subtotal = sum(
        money(item.get("subtotal"))
        for item in cart_items
    )

    shipping = (subtotal * Decimal("0.01")).quantize(
        Decimal("0.01")
    )

    total = subtotal + shipping

    return cart_items, subtotal, shipping, total


# ======================================================
# HOME
# ======================================================

@app.route("/")
def home():

    status, products = AdminQueries.getAllProducts(
        page_no=1,
        per_page=100
    )

    if not status:
        products = []

    products = [
        product for product in products
        if product.get("is_active", 1)
    ]

    return render_template(
        "home.html",
        products=products
    )


# ======================================================
# REGISTER
# ======================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        logging.info("User in register page")
        return render_template("register.html")

    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not all([name, email, password, confirm_password]):
        flash("Please fill all required fields", "err")
        return redirect(url_for("register"))

    if password != confirm_password:
        flash("Password Mismatch", "err")
        return redirect(url_for("register"))

    status, user = AuthQueries.getUserData(email=email)

    if status:
        flash("Email Already Exists", "err")
        logging.warning(f"{email} Email Already Exists")
        return redirect(url_for("register"))

    hash_password = bcrypt.hashpw(
        password=password.encode("utf-8"),
        salt=bcrypt.gensalt(4)
    )

    status, msg = AuthQueries.createUserAccount(
        name=name,
        email=email,
        password=hash_password,
        phone=phone
    )

    if not status:
        flash(msg, "err")
        logging.warning(msg)
        return redirect(url_for("register"))

    flash(msg, "msg")
    logging.info(msg)

    return redirect(url_for("login"))


# ======================================================
# LOGIN
# ======================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        logging.info("User in login page")
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        flash("Please enter email and password", "err")
        return redirect(url_for("login"))

    status, user = AuthQueries.getUserData(email=email)

    if not status:
        flash(user, "err")
        logging.warning(user)
        return redirect(url_for("login"))

    try:

        stored_password = user["hashpassword"]

        if isinstance(stored_password, memoryview):
            stored_password = stored_password.tobytes()

        if isinstance(stored_password, bytes):
            stored_password = stored_password.decode("utf-8")

        if stored_password.startswith(("scrypt:", "pbkdf2:")):

            verify_password_status = check_password_hash(
                stored_password,
                password
            )

        elif stored_password.startswith(("$2a$", "$2b$", "$2y$")):

            verify_password_status = bcrypt.checkpw(
                password.encode("utf-8"),
                stored_password.encode("utf-8")
            )

        else:
            verify_password_status = False

    except (ValueError, TypeError):
        logging.exception("Password verification error")
        verify_password_status = False

    if not verify_password_status:
        flash("Password incorrect", "err")
        logging.warning("Password incorrect")
        return redirect(url_for("login"))

    user_id = user.get("userid", user.get("user_id"))

    if user_id is None:
        flash("User ID not found", "err")
        return redirect(url_for("login"))

    session.clear()

    session["username"] = user["username"]
    session["role"] = user["role"]
    session["userid"] = user_id
    session["email"] = user["email"]

    if user["role"] == "admin":
        logging.info(f"{user['username']} entering admin dashboard")
        return redirect(url_for("admin_dashboard"))

    logging.info(f"{user['username']} entering products page")
    return redirect(url_for("products"))


# ======================================================
# LOGOUT
# ======================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully", "success")

    return redirect(url_for("home"))


# ======================================================
# PRODUCTS
# ======================================================

@app.route("/products")
def products():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    status, product_list = AdminQueries.getAllProducts(
        product_name=search,
        category=category,
        page_no=1,
        per_page=100
    )

    if not status or not product_list:
        product_list = []

    product_list = [
        product for product in product_list
        if product.get("is_active", 1)
    ]

    category_status, categories = AdminQueries.getAllCategories()

    if not category_status:
        categories = []

    return render_template(
        "user/products.html",
        products=product_list,
        categories=categories,
        search=search,
        selected_category=category
    )


# ======================================================
# PRODUCT DETAILS
# ======================================================

@app.route("/products/<int:product_id>/details")
def product_details(product_id):

    status, product = AdminQueries.getAllProducts(
        product_id=product_id
    )

    if not status or not product:
        abort(404)

    if not product.get("is_active", 1):
        abort(404)

    return render_template(
        "user/product_details.html",
        product=product
    )


# ======================================================
# CART
# ======================================================

@app.route("/cart")
@login_required
def cart():

    cart_items, subtotal, shipping, total = cart_summary(
        session["userid"]
    )

    return render_template(
        "user/cart.html",
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total
    )


# ======================================================
# ADD TO CART
# ======================================================

@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):

    quantity = request.form.get("quantity", 1)

    status, message = UserQueries.addCartItem(
        product_id,
        session["userid"],
        quantity
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(request.referrer or url_for("products"))


# ======================================================
# UPDATE CART
# ======================================================

@app.route("/cart/update/<int:cartid>", methods=["POST"])
@login_required
def update_cart(cartid):

    quantity = request.form.get("quantity", 1)

    status, message = UserQueries.updateCartItemQuantity(
        cartid,
        quantity,
        session["userid"]
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("cart"))


# ======================================================
# REMOVE CART ITEM
# ======================================================

@app.route("/cart/remove/<int:cartid>", methods=["POST"])
@login_required
def remove_cart(cartid):

    status, message = UserQueries.deleteCartItem(
        cartid,
        session["userid"]
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("cart"))

# ======================================================
# CHECKOUT
# ======================================================

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():

    userid = session["userid"]

    cart_items, subtotal, shipping, total = cart_summary(userid)

    if not cart_items:
        flash("Your cart is empty", "warning")
        return redirect(url_for("cart"))

    if request.method == "POST":

        address = request.form.get("address", "").strip()

        payment_method = request.form.get(
            "payment_method",
            "cash"
        ).strip().lower()

        if not address:
            flash("Please enter delivery address", "danger")
            return redirect(url_for("checkout"))

        # CASH ON DELIVERY
        if payment_method == "cash":

            status, result = UserQueries.createOrder(
                userid,
                address,
                "cash"
            )

            if status:
                flash("Order placed successfully!", "success")
                return redirect(url_for("orders"))

            flash(str(result), "danger")
            return redirect(url_for("checkout"))

        # RAZORPAY
        elif payment_method == "razorpay":

            try:

                client = razorpay_client()

                razorpay_order = client.order.create({
                    "amount": int(total * 100),
                    "currency": "INR",
                    "payment_capture": 1
                })

                status, result = UserQueries.createOrder(
                    userid,
                    address,
                    "razorpay",
                    razorpay_order["id"]
                )

                if not status:
                    flash(str(result), "danger")
                    return redirect(url_for("checkout"))

                session["pending_order_id"] = result["order_id"]

                return render_template(
                    "user/checkout.html",
                    cart_items=cart_items,
                    subtotal=subtotal,
                    shipping=shipping,
                    total=total,
                    razorpay_key_id=RAZORPAY_KEY_ID,
                    razorpay_order_id=razorpay_order["id"],
                    order_id=result["order_id"],
                    amount=int(total * 100)
                )

            except Exception:

                logging.exception("Razorpay checkout error")

                flash(
                    "Unable to initialize Razorpay payment",
                    "danger"
                )

                return redirect(url_for("checkout"))

        else:

            flash("Invalid payment method", "danger")
            return redirect(url_for("checkout"))

    return render_template(
        "user/checkout.html",
        cart_items=cart_items,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
        razorpay_key_id=RAZORPAY_KEY_ID
    )


# ======================================================
# RAZORPAY PAYMENT VERIFY
# ======================================================

@app.route("/payment/verify", methods=["POST"])
@login_required
def payment_verify():

    userid = session["userid"]

    order_id = request.form.get("order_id")
    razorpay_order_id = request.form.get("razorpay_order_id")
    razorpay_payment_id = request.form.get("razorpay_payment_id")
    razorpay_signature = request.form.get("razorpay_signature")

    if not all([
        order_id,
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature
    ]):
        flash("Payment details are missing", "danger")
        return redirect(url_for("orders"))

    try:

        order_id = int(order_id)

        if session.get("pending_order_id") != order_id:
            abort(403)

        client = razorpay_client()

        # VERIFY PAYMENT SIGNATURE
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        # FETCH PAYMENT DETAILS FROM RAZORPAY
        payment_details = client.payment.fetch(
            razorpay_payment_id
        )

        # VERIFY ORDER ID
        if payment_details.get("order_id") != razorpay_order_id:
            flash("Payment order ID mismatch", "danger")
            return redirect(url_for("orders"))

        # CHECK PAYMENT STATUS
        if payment_details.get("status") != "captured":
            flash(
                "Payment is not captured yet. Please check payment status.",
                "warning"
            )
            return redirect(url_for("orders"))

        # UPDATE DATABASE
        status, message = UserQueries.markPaid(
            userid,
            order_id,
            razorpay_order_id,
            razorpay_payment_id
        )

        if not status:

            logging.error(
                "Payment captured but database update failed: %s",
                message
            )

            flash(
                "Payment received, but order update is pending. Please contact support.",
                "warning"
            )

            return redirect(url_for("orders"))

        session.pop("pending_order_id", None)

        flash("Payment successful", "success")
        return redirect(url_for("orders"))
        

    except Exception:

        logging.exception("Payment verification error")

        # DO NOT CANCEL THE ORDER HERE.
        # Payment may already be captured in Razorpay.

        flash(
            "Payment verification could not be completed. Please check your order status.",
            "warning"
        )

        return redirect(url_for("orders"))



# ======================================================
# DOWNLOAD INVOICE
# ======================================================

@app.route("/invoice/<int:order_id>")
@login_required
def invoice(order_id):

    status, order = UserQueries.getOrderDetails(
        order_id,
        session["userid"]
    )

    if not status or not order:
        abort(404)

    return render_template(
        "user/invoice.html",
        order=order
    )


# ======================================================
# PAYMENT FAILED
# ======================================================

@app.route("/payment/failed", methods=["GET", "POST"])
@login_required
def payment_failed():

    order_id = request.values.get("order_id")

    if order_id:

        try:
            UserQueries.failPayment(
                session["userid"],
                int(order_id),
                "Payment failed"
            )
        except Exception:
            logging.exception("Payment failed update error")

    session.pop("pending_order_id", None)

    flash("Payment failed", "danger")

    return redirect(url_for("orders"))


# ======================================================
# CANCEL ORDER
# ======================================================

@app.route("/payment/cancel/<int:order_id>", methods=["POST"])
@login_required
def cancel_order(order_id):

    status, message = UserQueries.cancelPendingOrder(
        session["userid"],
        order_id
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    session.pop("pending_order_id", None)

    return redirect(url_for("orders"))


# ======================================================
# MY ORDERS
# ======================================================

@app.route("/orders")
@login_required
def orders():
    try:
        userid = session.get("userid")

        status, order_list = UserQueries.getOrders(userid)

        if not status:
            order_list = []

        return render_template(
            "user/orders.html",
            orders=order_list
        )

    except Exception as e:
        app.logger.exception("MY ORDERS PAGE ERROR")
        return "Orders Page Error: " + str(e), 500


# ======================================================
# ORDER DETAILS
# ======================================================

@app.route("/orders/<int:order_id>")
@login_required
def user_order_details(order_id):

    status, order = UserQueries.getOrderDetails(
        order_id,
        session["userid"]
    )

    if not status or not order:
        abort(404)

    return render_template(
        "user/order_details.html",
        order=order
    )


# ======================================================
# PROFILE
# ======================================================

@app.route("/profile")
@login_required
def profile():

    status, user = UserQueries.getUserProfile(
        session["userid"]
    )

    if not status or not user:
        abort(404)

    return render_template(
        "user/profile.html",
        user=user
    )


# ======================================================
# UPDATE PROFILE
# ======================================================

@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():

    username = request.form.get("username", "").strip()
    phone = request.form.get("phone", "").strip()
    dateofbirth = request.form.get("dateofbirth") or None

    if not username:
        flash("Username is required", "danger")
        return redirect(url_for("profile"))

    status, message = UserQueries.updateUserProfile(
        session["userid"],
        username,
        phone,
        dateofbirth
    )

    if status:
        session["username"] = username
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("profile"))


# ======================================================
# ADMIN DASHBOARD
# ======================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    user_status, users = AdminQueries.getUsers()

    product_status, products = AdminQueries.getAllProducts(
        page_no=1,
        per_page=1000
    )

    order_status, orders_list = AdminQueries.getOrders()

    total_users = len(users) if user_status else 0
    total_products = len(products) if product_status else 0
    total_orders = len(orders_list) if order_status else 0

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders
    )


# ======================================================
# ADMIN USERS
# ======================================================

@app.route("/admin/users")
@admin_required
def admin_users():

    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()

    status, users = AdminQueries.getUsers()

    if not status:
        users = []

    if search:

        search_lower = search.lower()

        users = [
            user for user in users
            if search_lower in str(user.get("username", "")).lower()
            or search_lower in str(user.get("email", "")).lower()
        ]

    if role:

        users = [
            user for user in users
            if user.get("role") == role
        ]

    return render_template(
        "admin/users.html",
        users=users,
        search=search,
        selected_role=role
    )


# ======================================================
# ADMIN USER DETAILS
# ======================================================

@app.route("/admin/users/<int:userid>")
@admin_required
def admin_user_details(userid):

    user = AdminQueries.getUserById(userid)

    if not user:
        abort(404)

    return render_template(
        "admin/user_details.html",
        user=user
    )


# ======================================================
# ADMIN USER STATUS
# ======================================================

@app.route("/admin/users/status/<int:userid>", methods=["POST"])
@admin_required
def admin_update_user_status(userid):

    is_active = request.form.get("is_active")

    if is_active is None:
        is_active = request.form.get("status", "1")

    is_active = str(is_active).lower() in [
        "1",
        "true",
        "active",
        "on"
    ]

    status, message = AdminQueries.updateUserStatus(
        userid,
        is_active
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("admin_users"))



# ======================================================
# ADMIN PRODUCTS
# ======================================================

@app.route("/admin/products")
@admin_required
def admin_products():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    page = request.args.get("page", 1, type=int)
    page = max(page, 1)

    result = AdminQueries.getProducts(
        search=search,
        category=category,
        page=page,
        per_page=7
    )

    products_list = result["products"]
    total = result["total"]
    categories = result["categories"]

    per_page = 7
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "admin/products.html",
        products=products_list,
        categories=categories,
        search=search,
        category=category,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        status="",
        stock="",
        min_price=None,
        max_price=None
    )




# ======================================================
# ADMIN ADD PRODUCT
# ======================================================

@app.route("/admin/add-product", methods=["GET", "POST"])
@admin_required
def admin_add_products():

    if request.method == "POST":

        product_name = request.form.get("name", "").strip()

        category = request.form.get("category", "").strip()
        new_category = request.form.get("new_category", "").strip()

        if new_category:
            category = new_category

        saleprice = request.form.get("price", "0")
        quantity = request.form.get("stock", "0")
        description = request.form.get("description", "").strip()

        image_file = request.files.get("image")

        # Validate product details
        if not product_name or not category:
            flash("Product name and category are required", "danger")
            return redirect(url_for("admin_add_products"))

        # Validate price and stock
        try:
            saleprice = Decimal(saleprice)
            quantity = int(quantity)

            if saleprice < 0 or quantity < 0:
                raise ValueError("Invalid price or stock")

        except Exception:
            flash("Enter valid price and stock", "danger")
            return redirect(url_for("admin_add_products"))

        # Upload image to Supabase Storage
        imgname = None
        storedpath = None

        if image_file and image_file.filename:

            if not allowed_file(image_file.filename):
                flash("Invalid image file", "danger")
                return redirect(url_for("admin_add_products"))

            imgname, storedpath = upload_product_image(image_file)

            if not imgname or not storedpath:
                flash("Image upload failed. Please try again.", "danger")
                return redirect(url_for("admin_add_products"))

        # Prepare product data
        product_data = (
            product_name,
            description,
            category,
            saleprice,
            quantity,
            imgname,
            storedpath
        )

        # Insert product into database
        status, message = AdminQueries.insertProductRecord(product_data)

        if status:
            flash(message, "success")
            return redirect(url_for("admin_products"))

        flash(message, "danger")

    # Load categories
    category_status, categories = AdminQueries.getAllCategories()

    if not category_status:
        categories = []

    return render_template(
        "admin/add_product.html",
        categories=categories
    )

# ======================================================
# ADMIN EDIT PRODUCT
# ======================================================

@app.route("/admin/edit-product/<int:product_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_product(product_id):

    product_status, product = AdminQueries.getAllProducts(
        product_id=product_id
    )

    if not product_status or not product:
        abort(404)

    if request.method == "POST":

        product_name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        saleprice = request.form.get("price", "0")
        quantity = request.form.get("stock", "0")
        description = request.form.get("description", "").strip()

        if not product_name or not category:
            flash("Product name and category are required", "danger")
            return redirect(
                url_for("admin_edit_product", product_id=product_id)
            )

        try:

            saleprice = Decimal(saleprice)
            quantity = int(quantity)

            if saleprice < 0 or quantity < 0:
                raise ValueError("Invalid values")

        except Exception:

            flash("Enter valid price and stock", "danger")
            return redirect(
                url_for("admin_edit_product", product_id=product_id)
            )

        product_data = (
            product_name,
            description,
            category,
            saleprice,
            quantity,
            product_id
        )

        status, message = AdminQueries.updateProductRecord(
            product_data
        )

        if status:
            flash(message, "success")
            return redirect(url_for("admin_products"))

        flash(message, "danger")

    category_status, categories = AdminQueries.getAllCategories()

    if not category_status:
        categories = []

    return render_template(
        "admin/edit_product.html",
        product=product,
        categories=categories
    )


# ======================================================
# ADMIN DELETE PRODUCT
# ======================================================

@app.route("/admin/delete-product/<int:product_id>", methods=["POST"])
@admin_required
def admin_delete_product(product_id):

    status, message = AdminQueries.deleteProduct(product_id)

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for("admin_products"))


# ======================================================
# ADMIN CATEGORIES
# ======================================================

@app.route("/admin/categories")
@admin_required
def admin_categories():

    status, categories = AdminQueries.getAllCategories()

    if not status:
        categories = []

    return render_template(
        "admin/category.html",
        categories=categories
    )


# ======================================================
# ADMIN ADD CATEGORY
# ======================================================

@app.route("/admin/add-category", methods=["POST"])
@admin_required
def admin_add_category():

    category = request.form.get("category", "").strip()
    new_category = request.form.get("new_category", "").strip()

    if new_category:
        category = new_category

    if not category:
        flash("Enter category name", "danger")
        return redirect(url_for("admin_categories"))

    flash(
        "Category will be added when you assign it to a product",
        "info"
    )

    return redirect(url_for("admin_categories"))


# ======================================================
# ADMIN EDIT CATEGORY
# ======================================================

@app.route("/admin/edit-category/<string:category_name>", methods=["POST"])
@admin_required
def admin_edit_category(category_name):

    flash("Edit the category through the product form", "info")

    return redirect(url_for("admin_categories"))


# ======================================================
# ADMIN DELETE CATEGORY
# ======================================================

@app.route("/admin/delete-category/<string:category_name>", methods=["POST"])
@admin_required
def admin_delete_category(category_name):

    flash(
        "Category cannot be deleted separately. Update its products first.",
        "warning"
    )

    return redirect(url_for("admin_categories"))


# ======================================================
# ADMIN ORDERS
# ======================================================

@app.route("/admin/orders")
@admin_required
def admin_orders():

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    status, orders_list = AdminQueries.getOrders(
        search=search,
        status=status_filter
    )

    if not status:
        orders_list = []

    return render_template(
        "admin/orders.html",
        orders=orders_list,
        search=search,
        selected_status=status_filter,
        page=1,
        total_pages=1
    )


# ======================================================
# ADMIN ORDER DETAILS
# ======================================================

@app.route("/admin/orders/<int:order_id>")
@admin_required
def admin_order_details(order_id):

    order = AdminQueries.getOrderDetails(order_id)

    if not order:
        abort(404)

    return render_template(
        "admin/order_details.html",
        order=order
    )


# ======================================================
# ADMIN UPDATE ORDER STATUS
# ======================================================

@app.route("/admin/orders/update-status/<int:order_id>", methods=["POST"])
@admin_required
def admin_update_order_status(order_id):

    order_status = request.form.get("status", "").strip().lower()

    status, message = AdminQueries.updateOrderStatus(
        order_id,
        order_status
    )

    if status:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(
        url_for(
            "admin_order_details",
            order_id=order_id
        )
    )


# ======================================================
# ERROR HANDLERS
# ======================================================

@app.errorhandler(403)
def forbidden(error):
    return render_template("404.html"), 403


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    logging.exception("Internal Server Error")
    return "Internal Server Error", 500


# ======================================================
# RUN APPLICATION
# ======================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
