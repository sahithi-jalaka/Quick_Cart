import os
import math
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "replace-this-secret-key")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}

def db_connection():
    return mysql.connector.connect(database=os.getenv("DB_NAME", "quick_cart"), **DB_CONFIG)

def initialize_database():
    # Create the database first, then its tables.
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS " + os.getenv("DB_NAME", "quick_cart"))
    cur.close()
    conn.close()

    conn = db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('customer','shop') NOT NULL,
            shop_name VARCHAR(150),
            latitude DECIMAL(10,7),
            longitude DECIMAL(10,7),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            shop_id INT NOT NULL,
            name VARCHAR(120) NOT NULL,
            description VARCHAR(255),
            price DECIMAL(10,2) NOT NULL,
            stock INT NOT NULL DEFAULT 0,
            FOREIGN KEY (shop_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_id INT NOT NULL,
            shop_id INT NOT NULL,
            status ENUM('Pending','Confirmed','Packed','Rejected','Collected') DEFAULT 'Pending',
            total DECIMAL(10,2) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES users(id),
            FOREIGN KEY (shop_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have permission to access that page.")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def query_all(sql, params=()):
    conn = db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None

def execute(sql, params=()):
    conn = db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    new_id = cur.lastrowid
    cur.close()
    conn.close()
    return new_id

def distance_km(lat1, lon1, lat2, lon2):
    # Haversine formula: approximate distance between two GPS coordinates.
    radius = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = math.radians(float(lat2) - float(lat1))
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * radius * math.asin(math.sqrt(a))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role")
        shop_name = request.form.get("shop_name", "").strip() if role == "shop" else None
        if not name or not email or len(password) < 6 or role not in ("customer", "shop"):
            flash("Enter valid details. Password must contain at least 6 characters.")
            return render_template("register.html")
        try:
            execute(
                """INSERT INTO users(name,email,password_hash,role,shop_name)
                   VALUES(%s,%s,%s,%s,%s)""",
                (name, email, generate_password_hash(password), role, shop_name)
            )
            flash("Registration successful. Please log in.")
            return redirect(url_for("login"))
        except Error:
            flash("That email may already be registered. Try another email.")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE email=%s", (email,))
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("customer_dashboard" if user["role"] == "customer" else "shop_dashboard"))
        flash("Incorrect email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/customer")
@login_required("customer")
def customer_dashboard():
    shops = query_all("""SELECT id, name, shop_name, latitude, longitude
                         FROM users WHERE role='shop'""")
    orders = query_all("""
        SELECT o.id,o.status,o.total,o.created_at,u.shop_name
        FROM orders o JOIN users u ON o.shop_id=u.id
        WHERE o.customer_id=%s ORDER BY o.id DESC
    """, (session["user_id"],))
    return render_template("customer.html", shops=shops, orders=orders)

@app.route("/nearby-shops", methods=["POST"])
@login_required("customer")
def nearby_shops():
    data = request.get_json(silent=True) or {}
    try:
        lat, lon = float(data["latitude"]), float(data["longitude"])
        radius = max(0.1, min(float(data.get("radius", 5)), 100))
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Valid location and radius are required."}), 400
    shops = query_all("""SELECT id, name, shop_name, latitude, longitude
                         FROM users WHERE role='shop' AND latitude IS NOT NULL
                         AND longitude IS NOT NULL""")
    result = []
    for shop in shops:
        d = distance_km(lat, lon, shop["latitude"], shop["longitude"])
        if d <= radius:
            shop["distance_km"] = round(d, 2)
            result.append(shop)
    result.sort(key=lambda x: x["distance_km"])
    return jsonify(result)

@app.route("/shop/location", methods=["POST"])
@login_required("shop")
def save_shop_location():
    data = request.get_json(silent=True) or {}
    try:
        lat, lon = float(data["latitude"]), float(data["longitude"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400
    execute("UPDATE users SET latitude=%s,longitude=%s WHERE id=%s",
            (lat, lon, session["user_id"]))
    return jsonify({"message": "Shop location saved."})

@app.route("/shop")
@login_required("shop")
def shop_dashboard():
    products = query_all("SELECT * FROM products WHERE shop_id=%s ORDER BY id DESC", (session["user_id"],))
    orders = query_all("""
        SELECT o.id,o.status,o.total,o.created_at,u.name AS customer_name
        FROM orders o JOIN users u ON o.customer_id=u.id
        WHERE o.shop_id=%s ORDER BY o.id DESC
    """, (session["user_id"],))
    return render_template("shop.html", products=products, orders=orders)

@app.route("/shop/product", methods=["POST"])
@login_required("shop")
def add_product():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    try:
        price, stock = float(request.form.get("price", 0)), int(request.form.get("stock", 0))
        if not name or price <= 0 or stock < 0:
            raise ValueError()
    except ValueError:
        flash("Enter a product name, positive price and valid stock.")
        return redirect(url_for("shop_dashboard"))
    execute("""INSERT INTO products(shop_id,name,description,price,stock)
               VALUES(%s,%s,%s,%s,%s)""",
            (session["user_id"], name, description, price, stock))
    flash("Product added.")
    return redirect(url_for("shop_dashboard"))

@app.route("/shop/product/delete/<int:product_id>", methods=["POST"])
@login_required("shop")
def delete_product(product_id):
    execute("DELETE FROM products WHERE id=%s AND shop_id=%s",
            (product_id, session["user_id"]))
    flash("Product deleted if it belonged to your shop.")
    return redirect(url_for("shop_dashboard"))

@app.route("/shop/<int:shop_id>/products")
@login_required("customer")
def shop_products(shop_id):
    shop = query_one("SELECT id,shop_name,name FROM users WHERE id=%s AND role='shop'", (shop_id,))
    if not shop:
        flash("Shop not found.")
        return redirect(url_for("customer_dashboard"))
    products = query_all("SELECT * FROM products WHERE shop_id=%s AND stock>0", (shop_id,))
    return render_template("products.html", shop=shop, products=products)

@app.route("/order/place", methods=["POST"])
@login_required("customer")
def place_order():
    shop_id = request.form.get("shop_id", type=int)
    quantities = request.form.getlist("quantity")
    product_ids = request.form.getlist("product_id")
    if not shop_id or len(quantities) != len(product_ids):
        flash("Please select products.")
        return redirect(url_for("customer_dashboard"))
    shop = query_one("SELECT id FROM users WHERE id=%s AND role='shop'", (shop_id,))
    if not shop:
        flash("Invalid shop.")
        return redirect(url_for("customer_dashboard"))
    conn = db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        total = 0
        items = []
        for pid, qty_text in zip(product_ids, quantities):
            qty = int(qty_text or 0)
            if qty <= 0:
                continue
            cur.execute("SELECT id,name,price,stock FROM products WHERE id=%s AND shop_id=%s",
                        (int(pid), shop_id))
            product = cur.fetchone()
            if not product or product["stock"] < qty:
                raise ValueError("A product is unavailable or has insufficient stock.")
            total += float(product["price"]) * qty
            items.append((product["id"], qty, product["price"]))
        if not items:
            raise ValueError("Choose at least one product.")
        cur.execute("INSERT INTO orders(customer_id,shop_id,total) VALUES(%s,%s,%s)",
                    (session["user_id"], shop_id, total))
        order_id = cur.lastrowid
        for pid, qty, price in items:
            cur.execute("""INSERT INTO order_items(order_id,product_id,quantity,unit_price)
                           VALUES(%s,%s,%s,%s)""", (order_id, pid, qty, price))
            cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s", (qty, pid))
        conn.commit()
        flash(f"Order #{order_id} placed successfully.")
    except (ValueError, Error) as exc:
        conn.rollback()
        flash(str(exc) if isinstance(exc, ValueError) else "Could not place order.")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("customer_dashboard"))

@app.route("/shop/order/<int:order_id>/<action>", methods=["POST"])
@login_required("shop")
def update_order(order_id, action):
    allowed = {"confirm": "Confirmed", "pack": "Packed", "reject": "Rejected"}
    if action not in allowed:
        flash("Invalid order action.")
        return redirect(url_for("shop_dashboard"))
    current = query_one("SELECT status FROM orders WHERE id=%s AND shop_id=%s",
                        (order_id, session["user_id"]))
    if not current:
        flash("Order not found.")
    elif action == "confirm" and current["status"] == "Pending":
        execute("UPDATE orders SET status='Confirmed' WHERE id=%s", (order_id,))
        flash("Order confirmed.")
    elif action == "pack" and current["status"] == "Confirmed":
        execute("UPDATE orders SET status='Packed' WHERE id=%s", (order_id,))
        flash("Order marked as packed.")
    elif action == "reject" and current["status"] == "Pending":
        execute("UPDATE orders SET status='Rejected' WHERE id=%s", (order_id,))
        flash("Order rejected. Contact the customer if a refund is required.")
    else:
        flash("That status change is not allowed.")
    return redirect(url_for("shop_dashboard"))

@app.route("/order/<int:order_id>")
@login_required("customer")
def order_detail(order_id):
    order = query_one("""SELECT o.*,u.shop_name FROM orders o
                         JOIN users u ON o.shop_id=u.id
                         WHERE o.id=%s AND o.customer_id=%s""",
                      (order_id, session["user_id"]))
    if not order:
        flash("Order not found.")
        return redirect(url_for("customer_dashboard"))
    items = query_all("""SELECT p.name,oi.quantity,oi.unit_price
                         FROM order_items oi JOIN products p ON oi.product_id=p.id
                         WHERE oi.order_id=%s""", (order_id,))
    return render_template("order_detail.html", order=order, items=items)

if __name__ == "__main__":
    try:
        initialize_database()
        print("Quick Cart database is ready.")
    except Error as exc:
        print("Database setup failed:", exc)
        print("Check MySQL is running and your .env credentials are correct.")
    app.run(debug=True)
