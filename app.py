from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "crud.db")

app = Flask(__name__)
app.secret_key = "ecommerce1233344"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db(seed_admin=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS Users_Table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    if seed_admin:
        admin_email = "admin@example.com"
        admin_pwd = "admin123"
        hashed = generate_password_hash(admin_pwd)
        try:
            c.execute("INSERT INTO Users_Table (email, password, role) VALUES (?, ?, ?)",
                      (admin_email, hashed, "admin"))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    conn.close()

init_db()

def query_user_by_email(email):
    db = get_db()
    return db.execute("SELECT * FROM Users_Table WHERE email = ?", (email,)).fetchone()

def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("products"))
        return func(*args, **kwargs)
    return wrapper

@app.route("/")
def root():
    if "user" in session:
        return redirect(url_for("products"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("products"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        if not email or not password:
            flash("Please provide both email and password.", "warning")
            return redirect(url_for("register"))
        if query_user_by_email(email):
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("login"))
        hashed = generate_password_hash(password)
        db = get_db()
        db.execute("INSERT INTO Users_Table (email, password, role) VALUES (?, ?, ?)",
                   (email, hashed, "user"))
        db.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("products"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        user = query_user_by_email(email)
        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))
        session["user"] = user["email"]
        session["role"] = user["role"]
        flash(f"Welcome back, {user['email']}!", "success")
        return redirect(url_for("products"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/products")
@login_required
def products():
    db = get_db()
    rows = db.execute("SELECT * FROM Products ORDER BY created_at DESC").fetchall()
    return render_template("products.html", products=rows)

@app.route("/products/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()
        if not name or price == "" or stock == "":
            flash("Please fill required fields (name, price, stock).", "warning")
            return redirect(url_for("add_product"))
        try:
            price_f = float(price)
            stock_i = int(stock)
        except ValueError:
            flash("Price must be a number and stock must be an integer.", "warning")
            return redirect(url_for("add_product"))
        now = datetime.utcnow().isoformat()
        db = get_db()
        db.execute("""INSERT INTO Products
                      (name, description, price, stock, created_at, updated_at)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   (name, description, price_f, stock_i, now, now))
        db.commit()
        flash("Product added successfully.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", action="Add", product=None)

@app.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM Products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("products"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        stock = request.form.get("stock", "").strip()
        if not name or price == "" or stock == "":
            flash("Please fill required fields (name, price, stock).", "warning")
            return redirect(url_for("edit_product", product_id=product_id))
        try:
            price_f = float(price)
            stock_i = int(stock)
        except ValueError:
            flash("Price must be a number and stock must be an integer.", "warning")
            return redirect(url_for("edit_product", product_id=product_id))
        now = datetime.utcnow().isoformat()
        db.execute("""UPDATE Products SET name=?, description=?, price=?, stock=?, updated_at=?
                      WHERE id=?""",
                   (name, description, price_f, stock_i, now, product_id))
        db.commit()
        flash("Product updated.", "success")
        return redirect(url_for("products"))
    return render_template("product_form.html", action="Edit", product=product)

@app.route("/products/delete/<int:product_id>", methods=["POST"])
@login_required
@admin_required
def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM Products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("products"))

@app.route("/products/<int:product_id>")
@login_required
def product_detail(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM Products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("products"))
    return render_template("product_detail.html", product=product)

if __name__ == "__main__":
    app.run(debug=True)
