from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import requests
import datetime
import random

app = Flask(__name__)
app.secret_key = "epin-super-gizli-anahtar-12345"

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1525268830635429930/Lwnf7QQj43IMSHJDrGgj68YpQc0ZKLZ5BF_0nPNQYTMegtVC0ZqlTcfROtV5iZtTmw98"
DATABASE = "market.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                balance REAL DEFAULT 0.0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                price REAL,
                image TEXT,
                stock INTEGER DEFAULT 234
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_title TEXT,
                price REAL,
                delivered_code TEXT,
                created_at TEXT
            )
        ''')
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO products (title, price, image, stock) VALUES (?, ?, ?, ?)",
                           ("Valorant 1200 VP", 150.0, "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", 234))
            cursor.execute("INSERT INTO products (title, price, image, stock) VALUES (?, ?, ?, ?)",
                           ("Steam 10 USD Cüzdan", 320.0, "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", 234))
            cursor.execute("INSERT INTO products (title, price, image, stock) VALUES (?, ?, ?, ?)",
                           ("PUBG Mobile 660 UC", 210.0, "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", 234))
        conn.commit()

init_db()

def get_current_user():
    if "user_id" not in session:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
        return cursor.fetchone()

def send_discord_log(title, description, color):
    if not DISCORD_WEBHOOK_URL or "BURAYA" in DISCORD_WEBHOOK_URL:
        return
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
    except Exception as e:
        print(f"Discord Hatası: {e}")

# Ana Sayfa (Giriş zorunlu DEĞİL - Herkes görebilir)
@app.route("/")
def home():
    user = get_current_user()
    balance = user["balance"] if user else 0.0
    username = user["username"] if user else None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        
    return render_template("index.html", balance=balance, username=username, products=products)

# Kayıt Ol
@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("home"))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Kullanıcı adı ve şifre zorunludur!", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, balance) VALUES (?, ?, 0.0)", (username, hashed_pw))
                conn.commit()
            flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Bu kullanıcı adı zaten kullanılıyor!", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

# Giriş Yap
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Giriş başarılı! Hoş geldin, {user['username']}", "success")
            return redirect(url_for("home"))
        else:
            flash("Kullanıcı adı veya şifre hatalı!", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# Çıkış Yap
@app.route("/logout")
def logout():
    session.clear()
    flash("Hesaptan çıkış yapıldı.", "info")
    return redirect(url_for("home"))

# Slot Çarkı
@app.route("/wheel")
def wheel():
    user = get_current_user()
    balance = user["balance"] if user else 0.0
    username = user["username"] if user else None
    return render_template("wheel.html", balance=balance, username=username)

@app.route("/spin", methods=["POST"])
def spin():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Çevirmek için lütfen önce giriş yapın veya kayıt olun!"}), 401

    data = request.get_json() or {}
    tier = data.get("tier", "bronze")
    tier_costs = {"bronze": 50.0, "silver": 150.0, "gold": 300.0}
    cost = tier_costs.get(tier, 50.0)

    if user["balance"] < cost:
        return jsonify({"success": False, "error": "Yetersiz bakiye! Lütfen önce bakiye yükleyin."}), 400

    options = [
        {"vp": "150 VP", "label": "150 Valorant Points"},
        {"vp": "600 VP", "label": "600 Valorant Points"},
        {"vp": "1200 VP", "label": "1200 Valorant Points"},
        {"vp": "2480 VP", "label": "2480 Valorant Points"},
        {"vp": "5350 VP", "label": "5350 Valorant Points"},
        {"vp": "11000 VP", "label": "11000 Valorant Points (BÜYÜK ÖDÜL)"}
    ]

    weights = [55, 30, 10, 4, 0.9, 0.1] if tier == "bronze" else ([15, 35, 30, 14, 5, 1] if tier == "silver" else [5, 15, 35, 25, 15, 5])
    chosen = random.choices(options, weights=weights, k=1)[0]
    
    p1 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
    p2 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
    code = f"VP-{p1}-{p2}"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (cost, user["id"]))
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute("INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES (?, ?, ?, ?, ?)",
                       (user["id"], f"Slot: {chosen['label']}", cost, code, now))
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user["id"],))
        new_balance = cursor.fetchone()["balance"]
        conn.commit()

    send_discord_log(
        title="🎰 Şans Slotu Çevrildi!",
        description=(
            f"**Kullanıcı:** `{user['username']}`\n"
            f"**Kasa:** {tier.upper()} ({cost:.2f} TL)\n"
            f"**Kazanılan:** 🎉 {chosen['vp']}\n"
            f"**Kod:** `{code}`\n"
            f"**Kalan Bakiye:** {new_balance:.2f} TL"
        ),
        color=15844367
    )

    return jsonify({
        "success": True,
        "reward": chosen["vp"],
        "reward_label": chosen["label"],
        "code": code,
        "new_balance": f"{new_balance:.2f}"
    })

# Bakiye Yükleme
@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    user = get_current_user()
    if not user:
        flash("Bakiye yüklemek için lütfen önce giriş yapın veya kayıt olun!", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = request.form.get("amount")
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash("Lütfen geçerli bir tutar girin!", "danger")
                return redirect(url_for("deposit"))
        except (ValueError, TypeError):
            flash("Geçersiz bakiye tutarı!", "danger")
            return redirect(url_for("deposit"))

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_val, user["id"]))
            cursor.execute("SELECT balance FROM users WHERE id = ?", (user["id"],))
            new_balance = cursor.fetchone()["balance"]
            conn.commit()

        trx_id = f"TRX{random.randint(100000, 999999)}"
        send_discord_log(
            title="💳 Yeni Bakiye Yüklendi!",
            description=f"**Kullanıcı:** `{user['username']}`\n**İşlem ID:** `{trx_id}`\n**Yüklenen:** {amount_val:.2f} TL\n**Güncel Bakiye:** {new_balance:.2f} TL",
            color=3066993
        )
        flash(f"💳 {amount_val:.2f} TL başarıyla yüklendi!", "success")
        return redirect(url_for("home"))

    return render_template("deposit.html", balance=user["balance"], username=user["username"])

# Satın Al
@app.route("/buy/<int:product_id>", methods=["POST"])
def buy(product_id):
    user = get_current_user()
    if not user:
        flash("Satın alma işlemi yapabilmek için lütfen giriş yapın veya kayıt olun!", "warning")
        return redirect(url_for("login"))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        
        if not product or product["stock"] <= 0:
            flash("Ürün stokta kalmadı!", "danger")
            return redirect(url_for("home"))

        if user["balance"] < product["price"]:
            flash("Yetersiz bakiye! Lütfen önce bakiye yükleyin.", "danger")
            return redirect(url_for("home"))

        raw_prefix = "".join([c for c in product["title"][:4] if c.isalnum()]).upper()
        prefix = raw_prefix if raw_prefix else "EPIN"
        part1 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        part2 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        delivered_code = f"{prefix}-{part1}-{part2}"

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (product["price"], user["id"]))
        cursor.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (product_id,))
        
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute("INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES (?, ?, ?, ?, ?)",
                       (user["id"], product["title"], product["price"], delivered_code, now))
        
        cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        remaining_stock = cursor.fetchone()["stock"]
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user["id"],))
        new_balance = cursor.fetchone()["balance"]
        conn.commit()

    send_discord_log(
        title="🛒 E-Pin Satışı Yapıldı",
        description=(
            f"**Kullanıcı:** `{user['username']}`\n"
            f"**Ürün:** {product['title']}\n"
            f"**Ödenen:** {product['price']:.2f} TL\n"
            f"**Kod:** `{delivered_code}`\n"
            f"**Kalan Stok:** {remaining_stock} Adet\n"
            f"**Kalan Bakiye:** {new_balance:.2f} TL"
        ),
        color=15158332
    )

    flash(f"🎉 Satın Alma Başarılı! Kodunuz: {delivered_code}", "success")
    return redirect(url_for("orders"))

# Siparişlerim
@app.route("/orders")
def orders():
    user = get_current_user()
    if not user:
        flash("Sipariş geçmişinizi görmek için lütfen giriş yapın!", "warning")
        return redirect(url_for("login"))

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user["id"],))
        order_list = cursor.fetchall()
    return render_template("orders.html", balance=user["balance"], username=user["username"], orders=order_list)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)