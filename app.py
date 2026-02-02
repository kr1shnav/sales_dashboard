from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

def get_db():
    return sqlite3.connect("database.db")

# ------------------ DATABASE SETUP ------------------
with get_db() as conn:
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        category TEXT,
        unit_price REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_date TEXT,
        product_id INTEGER,
        quantity INTEGER,
        total_sales REAL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)

    conn.commit()

# ------------------ DASHBOARD ------------------
@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        c = conn.cursor()

        c.execute("SELECT product_id, product_name FROM products")
        products = [{"id": r[0], "name": r[1]} for r in c.fetchall()]

        c.execute("""
            SELECT substr(order_date,1,7) AS month, SUM(total_sales)
            FROM sales
            WHERE user_id = ?
            GROUP BY month
            ORDER BY month
        """, (session["user_id"],))

        data = c.fetchall()

    months = [r[0] for r in data]
    revenue = [r[1] for r in data]

    return render_template(
        "dashboard.html",
        products=products,
        months=months,
        revenue=revenue
    )

# ------------------ ADD PRODUCT ------------------
@app.route("/add_product", methods=["POST"])
def add_product():
    data = request.form
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (product_name, category, unit_price) VALUES (?, ?, ?)",
            (data["name"], data["category"], data["price"])
        )
    return redirect("/")

# ------------------ ADD SALE ------------------
@app.route("/add_sale", methods=["POST"])
def add_sale():
    if "user_id" not in session:
        return redirect("/login")

    data = request.form

    with get_db() as conn:
        c = conn.cursor()

        price = c.execute(
            "SELECT unit_price FROM products WHERE product_id = ?",
            (data["product"],)
        ).fetchone()[0]

        total = int(data["quantity"]) * price

        c.execute("""
            INSERT INTO sales (user_id, order_date, product_id, quantity, total_sales)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            data["date"],
            data["product"],
            data["quantity"],
            total
        ))

    return redirect("/")

# ------------------ SIGNUP ------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if "user_id" in session:
        return redirect("/")

    if request.method == "POST":
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (
                        request.form["username"],
                        generate_password_hash(request.form["password"])
                    )
                )
            return redirect("/login")
        except sqlite3.IntegrityError:
            error = "Username already exists"

    return render_template("signup.html", error=error)

# ------------------ LOGIN ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if "user_id" in session:
        return redirect("/")

    if request.method == "POST":
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (request.form["username"],)
            ).fetchone()

        if user and check_password_hash(user[2], request.form["password"]):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/")
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)

# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

app.run(debug=True)
