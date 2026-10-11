
import os
import json
from datetime import datetime, timezone

from flask import (
    Flask, render_template, redirect, url_for,
    session, request, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "local-development-key-change-before-deployment"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///restaurant.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
csrf = CSRFProtect(app)


login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."



# ---------------- CUSTOMER ACCOUNT ----------------



class Customer(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Customer, int(user_id))


# ---------------- ORDER DATABASE ----------------

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customer.id"), nullable=False
    )
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    order_type = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.String(300), nullable=True)
    payment_method = db.Column(db.String(20), nullable=False)
    payment_status = db.Column(
        db.String(30), nullable=False, default="Pending"
    )
    status = db.Column(db.String(30), nullable=False, default="Pending")
    items_json = db.Column(db.Text, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# ---------------- RESTAURANT MENU ----------------

menu_items = [
    {
        "id": 1,
        "name": "Chicken and Chips",
        "description": "Crispy chicken served with golden chips.",
        "price": 450,
        "emoji": "🍗",
    },
    {
        "id": 2,
        "name": "Beef Burger",
        "description": "Juicy beef burger with fresh vegetables.",
        "price": 350,
        "emoji": "🍔",
    },
    {
        "id": 3,
        "name": "Pilau",
        "description": "Swahili-style spiced rice with beef.",
        "price": 300,
        "emoji": "🍛",
    },
    {
        "id": 4,
        "name": "Fish and Ugali",
        "description": "A delicious coastal fish meal with ugali.",
        "price": 500,
        "emoji": "🐟",
    },
    {
        "id": 5,
        "name": "Chips and Sausage",
        "description": "Hot chips served with sausage.",
        "price": 250,
        "emoji": "🍟",
    },
    {
        "id": 6,
        "name": "Fresh Juice",
        "description": "A refreshing fruit juice.",
        "price": 150,
        "emoji": "🥤",
    },
]


def get_cart_details():
    """Calculate cart prices from the server's menu, not browser-submitted prices."""
    cart = session.get("cart", {})
    cart_items = []
    total = 0

    for meal in menu_items:
        try:
            quantity = int(cart.get(str(meal["id"]), 0))
        except (TypeError, ValueError):
            quantity = 0

        quantity = max(0, min(quantity, 50))

        if quantity > 0:
            subtotal = meal["price"] * quantity
            cart_items.append({
                **meal,
                "quantity": quantity,
                "subtotal": subtotal,
            })
            total += subtotal

    return cart_items, total


# ---------------- HOME AND CART ----------------

@app.route("/")
def home():
    cart_count = sum(
        int(quantity) for quantity in session.get("cart", {}).values()
        if str(quantity).isdigit()
    )
    return render_template(
        "index.html",
        menu_items=menu_items,
        cart_count=cart_count,
    )


@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    item_id = request.form.get("item_id", type=int)
    item = next((meal for meal in menu_items if meal["id"] == item_id), None)

    if item is None:
        flash("That menu item could not be found.", "error")
        return redirect(url_for("home"))

    cart = session.get("cart", {})
    key = str(item_id)

    try:
        quantity = int(cart.get(key, 0))
    except (TypeError, ValueError):
        quantity = 0

    if quantity >= 50:
        flash("You have reached the quantity limit for this meal.", "error")
    else:
        cart[key] = quantity + 1
        session["cart"] = cart
        flash("Meal added to your cart.", "success")

    return redirect(url_for("home"))


@app.route("/cart")
def view_cart():
    cart_items, total = get_cart_details()
    return render_template(
        "cart.html",
        cart_items=cart_items,
        total=total
    )


@app.route("/remove-from-cart", methods=["POST"])
def remove_from_cart():
    item_id = request.form.get("item_id", type=int)
    cart = session.get("cart", {})
    cart.pop(str(item_id), None)
    session["cart"] = cart
    return redirect(url_for("view_cart"))


# ---------------- CUSTOMER REGISTRATION ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not email or not password:
            flash("Please fill in every field.", "error")
        elif len(full_name) > 100 or len(email) > 120:
            flash("Your name or email is too long.", "error")
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Please enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        else:
            customer = Customer(full_name=full_name, email=email)
            customer.set_password(password)
            db.session.add(customer)

            try:
                db.session.commit()
                login_user(customer)
                flash("Your account has been created successfully!", "success")
                return redirect(url_for("home"))
            except IntegrityError:
                db.session.rollback()
                flash("An account with that email already exists.", "error")

    return render_template("register.html")


# ---------------- CUSTOMER LOGIN ----------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        customer = Customer.query.filter_by(email=email).first()

        if customer and customer.check_password(password):
            login_user(customer)
            print("LOGIN SUCCESS:", customer.email)
            print("ADMIN FLAG:", customer.is_admin)
            flash("Welcome back!", "success")
            return redirect(url_for("home"))

        print("LOGIN FAILED for email:", email)
        flash("Email or password is incorrect.", "error")

    return render_template("login.html")


# ---------------- ADMINISTRATOR LOGIN ----------------

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        administrator = Customer.query.filter_by(
            email=email,
            is_admin=True
        ).first()

        if administrator and administrator.check_password(password):
            login_user(administrator)
            flash("Administrator login successful!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid administrator email or password.", "error")

    return render_template("admin_login.html")



# ---------------- CHECKOUT AND ORDER PLACEMENT ----------------

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart_items, total = get_cart_details()

    if not cart_items:
        flash("Your cart is empty. Please choose a meal first.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        order_type = request.form.get("order_type", "")
        payment_method = request.form.get("payment_method", "")
        phone = request.form.get("phone", "").strip()
        delivery_address = request.form.get("delivery_address", "").strip()

        if order_type not in ("dine_in", "delivery"):
            flash("Please choose dine-in or delivery.", "error")
        elif payment_method not in ("cash", "mpesa"):
            flash("Please choose Cash or M-Pesa.", "error")
        elif not phone or len(phone) > 30:
            flash("Please enter a valid contact phone number.", "error")
        elif order_type == "delivery" and not delivery_address:
            flash("Please enter the delivery address.", "error")
        elif len(delivery_address) > 300:
            flash("The delivery address is too long.", "error")
        else:
            # Store a snapshot of meal names, quantities and prices.
            order_snapshot = [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "subtotal": item["subtotal"],
                }
                for item in cart_items
            ]

            new_order = Order(
                customer_id=current_user.id,
                customer_name=current_user.full_name,
                phone=phone,
                order_type=order_type,
                delivery_address=(
                    delivery_address if order_type == "delivery" else None
                ),
                payment_method=payment_method,
                payment_status="Pending" if payment_method == "mpesa" else "Pay on collection/delivery",
                status="Pending",
                items_json=json.dumps(order_snapshot),
                total=total,
            )

            db.session.add(new_order)
            db.session.commit()

            # Empty the cart only after the order has been saved.
            session["cart"] = {}

            return redirect(
                url_for("order_confirmation", order_id=new_order.id)
            )

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total,
        customer=current_user,
    )


@app.route("/order/<int:order_id>")
@login_required
def order_confirmation(order_id):
    order = db.session.get(Order, order_id)

    if order is None or order.customer_id != current_user.id:
        abort(404)

    order_items = json.loads(order.items_json)

    return render_template(
        "order_confirmation.html",
        order=order,
        order_items=order_items,
    )

# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "success")
    return redirect(url_for("home"))


# ---------------- ADMIN DASHBOARD ----------------

ALLOWED_ORDER_STATUSES = (
    "Pending",
    "Preparing",
    "Ready",
    "Served",
)


@app.route("/admin")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)

    orders = Order.query.order_by(Order.created_at.desc()).all()

    for order in orders:
        order.display_items = json.loads(order.items_json)

    return render_template(
        "admin_dashboard.html",
        orders=orders,
        statuses=ALLOWED_ORDER_STATUSES,
    )


@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@login_required
def update_order_status(order_id):
    if not current_user.is_admin:
        abort(403)

    order = db.session.get(Order, order_id)

    if order is None:
        abort(404)

    new_status = request.form.get("status", "")

    if new_status not in ALLOWED_ORDER_STATUSES:
        abort(400)

    order.status = new_status
    db.session.commit()

    flash(
        f"Order #{order.id} status updated to {new_status}.",
        "success",
    )
    return redirect(url_for("admin_dashboard"))

# ---------------- CREATE DATABASE TABLES ----------------

with app.app_context():
    db.create_all()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
