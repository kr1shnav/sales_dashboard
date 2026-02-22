from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

def get_db():
    return sqlite3.connect("database.db")

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

@app.route("/")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        products = pd.read_sql_query(
            "SELECT product_id, product_name FROM products",
            conn
        )

    product_list = products.to_dict(orient="records")

    return render_template(
        "dashboard.html",
        products=product_list
    )

@app.route("/add_product", methods=["POST"])
def add_product():
    if "user_id" not in session:
        return redirect("/login")

    data = request.form
    with get_db() as conn:
        conn.execute(
            "INSERT INTO products (product_name, category, unit_price) VALUES (?, ?, ?)",
            (data["name"], data["category"], data["price"])
        )
    return redirect("/")

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

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect("/login")

    img_dir = "static/images"
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)

    # ── Shared colour palette ────────────────────────────────────────────────
    COLORS = ["#4361ee", "#4895ef", "#2ec4b6", "#7c3aed", "#f59e0b", "#ef4444", "#10b981", "#f97316"]

    with get_db() as conn:
        df = pd.read_sql_query("""
            SELECT s.order_date, s.quantity, s.total_sales,
                   p.product_name, p.category
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE s.user_id = ?
            ORDER BY s.order_date DESC
        """, conn, params=(session["user_id"],))

    charts = {"monthly": None, "top_products": None, "category": None}
    stats  = {"total_revenue": 0.0, "total_sales": 0, "avg_order": 0.0, "top_product": None}

    if not df.empty:
        # ── KPIs ────────────────────────────────────────────────────────────────
        stats["total_revenue"] = float(df["total_sales"].sum())
        stats["total_sales"]   = len(df)
        stats["avg_order"]     = float(df["total_sales"].mean())
        top = df.groupby("product_name")["total_sales"].sum().idxmax()
        stats["top_product"]   = top

        # ── Helper: common figure style ─────────────────────────────────────────
        def styled_fig(w=12, h=4):
            fig, ax = plt.subplots(figsize=(w, h), dpi=120)
            ax.set_facecolor("#f8fafc")
            fig.patch.set_facecolor("white")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#e2e8f0")
            ax.spines["bottom"].set_color("#e2e8f0")
            ax.tick_params(colors="#94a3b8", labelsize=9)
            ax.yaxis.label.set_color("#94a3b8")
            ax.xaxis.label.set_color("#94a3b8")
            ax.title.set_color("#0f172a")
            return fig, ax

        # ── 1. Monthly Revenue ───────────────────────────────────────────────────
        df_m = df.copy()
        df_m["order_date"] = pd.to_datetime(df_m["order_date"])
        df_m["month"] = df_m["order_date"].dt.to_period("M")
        monthly = df_m.groupby("month")["total_sales"].sum().sort_index()

        fig, ax = styled_fig(12, 4)
        ax.plot(monthly.index.astype(str), monthly.values,
                color=COLORS[0], linewidth=2.5, marker="o",
                markersize=6, markerfacecolor="white", markeredgewidth=2)
        ax.fill_between(monthly.index.astype(str), monthly.values,
                        alpha=0.12, color=COLORS[0])
        ax.set_title("Monthly Revenue", fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel("Month", fontsize=9)
        ax.set_ylabel("Revenue ($)", fontsize=9)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        path = f"{img_dir}/monthly.png"
        plt.savefig(path, bbox_inches="tight")
        plt.close()
        charts["monthly"] = path

        # ── 2. Top Products ──────────────────────────────────────────────────────
        top_products = (df.groupby("product_name")["total_sales"]
                          .sum().nlargest(8).sort_values())
        fig, ax = styled_fig(8, max(4, len(top_products) * 0.65))
        bars = ax.barh(top_products.index, top_products.values,
                       color=COLORS[:len(top_products)], height=0.55)
        for bar, val in zip(bars, top_products.values):
            ax.text(bar.get_width() + top_products.values.max() * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"${val:,.0f}", va="center", fontsize=8.5,
                    color="#475569", fontweight="600")
        ax.set_title("Top Products by Revenue", fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel("Revenue ($)", fontsize=9)
        ax.set_xlim(0, top_products.values.max() * 1.18)
        plt.tight_layout()
        path = f"{img_dir}/top_products.png"
        plt.savefig(path, bbox_inches="tight")
        plt.close()
        charts["top_products"] = path

        # ── 3. Category Pie ──────────────────────────────────────────────────────
        by_cat = df.groupby("category")["total_sales"].sum()
        fig, ax = styled_fig(7, 5)
        wedges, texts, autotexts = ax.pie(
            by_cat.values,
            labels=by_cat.index,
            autopct="%1.1f%%",
            startangle=140,
            colors=COLORS[:len(by_cat)],
            pctdistance=0.78,
            wedgeprops=dict(linewidth=2, edgecolor="white")
        )
        for t in texts:     t.set_fontsize(9);  t.set_color("#475569")
        for t in autotexts: t.set_fontsize(8.5); t.set_color("white"); t.set_fontweight("700")
        ax.set_title("Revenue by Category", fontsize=13, fontweight="bold", pad=14)
        plt.tight_layout()
        path = f"{img_dir}/category.png"
        plt.savefig(path, bbox_inches="tight")
        plt.close()
        charts["category"] = path

    # ── Recent sales table ───────────────────────────────────────────────────
    recent_sales = df.head(20).to_dict(orient="records") if not df.empty else []

    return render_template("analytics.html",
                           stats=stats,
                           charts=charts,
                           recent_sales=recent_sales)


if __name__ == "__main__":
    app.run(debug=True)

