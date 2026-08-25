from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import requests
import datetime
import random

app = Flask(__name__)
app.secret_key = "gizli-epin-anahtari"

# Discord Webhook Linki
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
                balance REAL DEFAULT 500.0
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
        cursor.execute("INSERT OR IGNORE INTO users (id, username, balance) VALUES (1, 'Oyuncu', 500.0)")
        
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

@app.route("/")
def home():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        balance = cursor.fetchone()["balance"]
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
    return render_template("index.html", balance=balance, products=products)

# Slot / Şans Çarkı Sayfası
@app.route("/wheel")
def wheel():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        balance = cursor.fetchone()["balance"]
    return render_template("wheel.html", balance=balance)

# Slot Çevirme API İsteği (Ajax)
@app.route("/spin", methods=["POST"])
def spin():
    data = request.get_json() or {}
    tier = data.get("tier", "bronze") # bronze (50 TL), silver (150 TL), gold (300 TL)

    tier_costs = {
        "bronze": 50.0,
        "silver": 150.0,
        "gold": 300.0
    }
    cost = tier_costs.get(tier, 50.0)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        balance = cursor.fetchone()["balance"]

        if balance < cost:
            return jsonify({"success": False, "error": "Yetersiz bakiye! Lütfen bakiye yükleyin."}), 400

        # İhtimal Havuzu (Yatırılan tutara göre ağırlıklar)
        # VP Seçenekleri: 150 VP, 600 VP, 1200 VP, 2480 VP, 5350 VP, 11000 VP
        options = [
            {"vp": "150 VP", "label": "150 Valorant Points"},
            {"vp": "600 VP", "label": "600 Valorant Points"},
            {"vp": "1200 VP", "label": "1200 Valorant Points"},
            {"vp": "2480 VP", "label": "2480 Valorant Points"},
            {"vp": "5350 VP", "label": "5350 Valorant Points"},
            {"vp": "11000 VP", "label": "11000 Valorant Points (BÜYÜK ÖDÜL)"}
        ]

        if tier == "bronze":  # 50 TL
            weights = [55, 30, 10, 4, 0.9, 0.1]
        elif tier == "silver": # 150 TL
            weights = [15, 35, 30, 14, 5, 1]
        else: # gold - 300 TL
            weights = [5, 15, 35, 25, 15, 5]

        # Ağırlıklı rastgele seçim
        chosen = random.choices(options, weights=weights, k=1)[0]
        
        # Kod Üret
        p1 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        p2 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        code = f"VP-{p1}-{p2}"

        # Bakiyeyi Düş ve Siparişe Ekle
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = 1", (cost,))
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        item_title = f"Slot Çarkı: {chosen['label']}"
        cursor.execute("INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES (1, ?, ?, ?, ?)",
                       (item_title, cost, code, now))
        
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        new_balance = cursor.fetchone()["balance"]
        conn.commit()

    # Discord Log
    send_discord_log(
        title="🎰 Şans Çarkı / Slot Çevrildi!",
        description=(
            f"**Seçilen Kasa:** {tier.upper()} ({cost:.2f} TL)\n"
            f"**Kazanılan Ödül:** 🎉 {chosen['vp']}\n"
            f"**Teslim Edilen Kod:** `{code}`\n"
            f"**Kalan Kullanıcı Bakiyesi:** {new_balance:.2f} TL"
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

@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    with get_db() as conn:
        cursor = conn.cursor()
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

            cursor.execute("UPDATE users SET balance = balance + ? WHERE id = 1", (amount_val,))
            cursor.execute("SELECT balance FROM users WHERE id = 1")
            new_balance = cursor.fetchone()["balance"]
            conn.commit()

            trx_id = f"TRX{random.randint(100000, 999999)}"
            send_discord_log(
                title="💳 Yeni Bakiye Yüklendi!",
                description=f"**İşlem ID:** `{trx_id}`\n**Yüklenen Tutar:** {amount_val:.2f} TL\n**Güncel Bakiye:** {new_balance:.2f} TL",
                color=3066993
            )
            flash(f"💳 {amount_val:.2f} TL başarıyla yüklendi!", "success")
            return redirect(url_for("home"))

        cursor.execute("SELECT balance FROM users WHERE id = 1")
        balance = cursor.fetchone()["balance"]
    return render_template("deposit.html", balance=balance)

@app.route("/buy/<int:product_id>", methods=["POST"])
def buy(product_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        user_balance = cursor.fetchone()["balance"]
        
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        
        if not product or product["stock"] <= 0 or user_balance < product["price"]:
            flash("İşlem gerçekleştirilemedi!", "danger")
            return redirect(url_for("home"))

        raw_prefix = "".join([c for c in product["title"][:4] if c.isalnum()]).upper()
        prefix = raw_prefix if raw_prefix else "EPIN"
        part1 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        part2 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
        delivered_code = f"{prefix}-{part1}-{part2}"

        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = 1", (product["price"],))
        cursor.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (product_id,))
        
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute("INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES (1, ?, ?, ?, ?)",
                       (product["title"], product["price"], delivered_code, now))
        
        cursor.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        remaining_stock = cursor.fetchone()["stock"]
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        new_balance = cursor.fetchone()["balance"]
        conn.commit()

    send_discord_log(
        title="🛒 E-Pin Teslimatı Yapıldı",
        description=(
            f"**Ürün:** {product['title']}\n"
            f"**Ödenen Tutar:** {product['price']:.2f} TL\n"
            f"**Teslim Edilen Kod:** `{delivered_code}`\n"
            f"**Kalan Stok:** {remaining_stock} Adet\n"
            f"**Kalan Bakiye:** {new_balance:.2f} TL"
        ),
        color=15158332
    )

    flash(f"🎉 Satın Alma Başarılı! {product['title']} Kodunuz: {delivered_code}", "success")
    return redirect(url_for("orders"))

@app.route("/orders")
def orders():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = 1")
        balance = cursor.fetchone()["balance"]
        cursor.execute("SELECT * FROM orders WHERE user_id = 1 ORDER BY id DESC")
        order_list = cursor.fetchall()
    return render_template("orders.html", balance=balance, orders=order_list)

if __name__ == "__main__":
    app.run(debug=True)