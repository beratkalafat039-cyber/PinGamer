from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
import requests
import datetime
import random
import sqlite3

app = Flask(__name__)
app.secret_key = "epin-super-gizli-anahtar-12345"

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1525268830635429930/Lwnf7QQj43IMSHJDrGgj68YpQc0ZKLZ5BF_0nPNQYTMegtVC0ZqlTcfROtV5iZtTmw98"
DATABASE_URL = os.environ.get("DATABASE_URL")

HAS_POSTGRES = False
if DATABASE_URL:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        HAS_POSTGRES = True
    except Exception as e:
        print(f"PostgreSQL modülü yüklenemedi: {e}")

def get_db():
    if HAS_POSTGRES and DATABASE_URL:
        try:
            return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"PostgreSQL bağlantı hatası: {e}")
    
    conn = sqlite3.connect("market.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if HAS_POSTGRES and DATABASE_URL:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE,
                    password TEXT,
                    balance REAL DEFAULT 0.0
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    price REAL,
                    image TEXT,
                    stock INTEGER DEFAULT 234
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    product_title TEXT,
                    price REAL,
                    delivered_code TEXT,
                    created_at TEXT
                );
            ''')
            conn.commit()

            urunler = [
                ("Valorant 1200 VP", 150.0, "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", 234),
                ("Steam 10 USD Cüzdan", 320.0, "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", 234),
                ("PUBG Mobile 660 UC", 210.0, "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", 234)
            ]
            for title, price, img, stock in urunler:
                cursor.execute("SELECT id FROM products WHERE title = %s", (title,))
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE products SET price = %s, image = %s, stock = %s WHERE title = %s", (price, img, stock, title))
                else:
                    cursor.execute("INSERT INTO products (title, price, image, stock) VALUES (%s, %s, %s, %s)", (title, price, img, stock))
            conn.commit()
        else:
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
            conn.commit()

            urunler = [
                ("Valorant 1200 VP", 150.0, "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", 234),
                ("Steam 10 USD Cüzdan", 320.0, "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", 234),
                ("PUBG Mobile 660 UC", 210.0, "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", 234)
            ]
            for title, price, img, stock in urunler:
                cursor.execute("SELECT id FROM products WHERE title = ?", (title,))
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE products SET price = ?, image = ?, stock = ? WHERE title = ?", (price, img, stock, title))
                else:
                    cursor.execute("INSERT INTO products (title, price, image, stock) VALUES (?, ?, ?, ?)", (title, price, img, stock))
            conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Veritabanı başlatma hatası: {e}")

init_db()

# --- BANKA VE POS STANDARTLARINDA KART DOĞRULAMA (BIN + LUHN) ---
TURKISH_BINS = {
    # Ziraat Bankası
    "454671": ("Ziraat Bankası", "Visa"),
    "542374": ("Ziraat Bankası", "Mastercard"),
    "979201": ("Ziraat Bankası", "Troy"),
    # İş Bankası Maximum
    "454359": ("Türkiye İş Bankası", "Visa"),
    "454360": ("Türkiye İş Bankası", "Visa"),
    "589283": ("Türkiye İş Bankası", "Mastercard"),
    # Garanti BBVA Bonus
    "540036": ("Garanti BBVA", "Mastercard"),
    "517041": ("Garanti BBVA", "Mastercard"),
    "554960": ("Garanti BBVA", "Mastercard"),
    "405040": ("Garanti BBVA", "Visa"),
    # Akbank Axess
    "552608": ("Akbank", "Mastercard"),
    "589004": ("Akbank", "Mastercard"),
    "435509": ("Akbank", "Visa"),
    "979207": ("Akbank", "Troy"),
    # Yapı Kredi World
    "545103": ("Yapı Kredi", "Mastercard"),
    "516888": ("Yapı Kredi", "Mastercard"),
    "450634": ("Yapı Kredi", "Visa"),
    # VakıfBank
    "491005": ("VakıfBank", "Visa"),
    "415792": ("VakıfBank", "Visa"),
    "542119": ("VakıfBank", "Mastercard"),
    "979288": ("VakıfBank", "Troy"),
    # QNB Finansbank
    "531157": ("QNB Finansbank", "Mastercard"),
    "498749": ("QNB Finansbank", "Visa"),
    "415565": ("QNB Finansbank", "Visa"),
    # Halkbank Paraf
    "447505": ("Halkbank", "Visa"),
    "552879": ("Halkbank", "Mastercard"),
    "453144": ("Halkbank", "Visa"),
    # DenizBank
    "460345": ("DenizBank", "Visa"),
    "476662": ("DenizBank", "Visa"),
    "520019": ("DenizBank", "Mastercard"),
    # Papara / Paycell / Tosla / İninal
    "404809": ("Papara Card", "Mastercard"),
    "543719": ("Paycell", "Mastercard"),
    "516741": ("Tosla", "Mastercard"),
    "454314": ("İninal", "Visa")
}

def validate_credit_card(card_holder, card_number, exp_date, cvv):
    # 1. Ad Soyad Kontrolü
    names = [n for n in card_holder.strip().split() if len(n) >= 2]
    if len(names) < 2:
        return False, "Kart üzerindeki isim ve soyisim eksiksiz girilmelidir.", None, None

    # 2. Rakam ve Hane Temizleme
    clean_num = re.sub(r"\D", "", card_number)
    if len(clean_num) != 16:
        return False, "Kredi kartı numarası tam olarak 16 haneli olmalıdır.", None, None

    # 3. BIN ve Banka Doğrulaması (İlk 6 Hane)
    bin_code = clean_num[:6]
    bank_info = TURKISH_BINS.get(bin_code)
    
    if not bank_info:
        # Genel Şema Kontrolü (Visa/Mastercard/Troy)
        if clean_num.startswith("4"):
            bank_name, card_brand = "Visa Kart", "Visa"
        elif any(clean_num.startswith(str(p)) for p in range(51, 56)) or any(clean_num.startswith(str(p)) for p in range(2221, 2721)):
            bank_name, card_brand = "Mastercard", "Mastercard"
        elif clean_num.startswith("9792"):
            bank_name, card_brand = "Troy Kart", "Troy"
        else:
            return False, "Geçersiz kart numarası! Tanımlanamayan Banka / BIN kodu.", None, None
    else:
        bank_name, card_brand = bank_info

    # 4. Mod-10 Luhn Algoritması
    checksum = 0
    reverse_digits = [int(d) for d in clean_num[::-1]]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += (doubled - 9) if doubled > 9 else doubled
        else:
            checksum += digit
    if checksum % 10 != 0:
        return False, "Kart numarası geçersiz! (Luhn algoritması kontrolünden geçemedi)", None, None

    # 5. Son Kullanma Tarihi Doğrulaması (AA/YY)
    exp_clean = exp_date.strip().replace(" ", "")
    if not re.match(r"^(0[1-9]|1[0-2])\/?([0-9]{2})$", exp_clean):
        return False, "Son kullanma tarihi geçersiz formatta! (Örn: 12/28)", None, None

    parts = exp_clean.split("/") if "/" in exp_clean else [exp_clean[:2], exp_clean[2:]]
    month, year = int(parts[0]), int(f"20{parts[1]}")
    
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month

    if year < current_year or (year == current_year and month < current_month):
        return False, "Kartınızın son kullanma tarihi dolmuştur.", None, None

    # 6. CVV Kontrolü
    if not (cvv.isdigit() and len(cvv) == 3):
        return False, "CVV güvenlik kodu 3 haneli sayı olmalıdır.", None, None

    return True, "Geçerli", bank_name, card_brand

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"SELECT * FROM users WHERE id = {p}", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        print(f"Kullanıcı getirme hatası: {e}")
        return None

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
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
        
    return render_template("index.html", balance=balance, username=username, products=products)

@app.route("/register", methods=["GET", "POST"])
def register():
    user = get_current_user()
    if user:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Kullanıcı adı ve şifre zorunludur!", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        try:
            cursor.execute(f"INSERT INTO users (username, password, balance) VALUES ({p}, {p}, 0.0)", (username, hashed_pw))
            conn.commit()
            flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for("login"))
        except Exception:
            flash("Bu kullanıcı adı zaten kullanılıyor!", "danger")
            return redirect(url_for("register"))
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    user = get_current_user()
    if user:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"SELECT * FROM users WHERE username = {p}", (username,))
        user_record = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_record and user_record["password"] and check_password_hash(user_record["password"], password):
            session.clear()
            session["user_id"] = user_record["id"]
            session["username"] = user_record["username"]
            session.permanent = True
            flash(f"Giriş başarılı! Hoş geldin, {user_record['username']}", "success")
            return redirect(url_for("home"))
        else:
            flash("Kullanıcı adı veya şifre hatalı!", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Hesaptan çıkış yapıldı.", "info")
    return redirect(url_for("login"))

@app.route("/wheel")
def wheel():
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None
    return render_template("wheel.html", balance=balance, username=username)

@app.route("/spin", methods=["POST"])
def spin():
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "Çevirmek için lütfen önce giriş yapın!"}), 401

    data = request.get_json() or {}
    tier = data.get("tier", "bronze")
    tier_costs = {"bronze": 50.0, "silver": 150.0, "gold": 300.0}
    cost = tier_costs.get(tier, 50.0)

    current_balance = float(user["balance"] or 0.0)
    if current_balance < cost:
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

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    
    cursor.execute(f"UPDATE users SET balance = balance - {p} WHERE id = {p}", (cost, user["id"]))
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute(f"INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES ({p}, {p}, {p}, {p}, {p})",
                   (user["id"], f"Slot: {chosen['label']}", cost, code, now))
    cursor.execute(f"SELECT balance FROM users WHERE id = {p}", (user["id"],))
    row = cursor.fetchone()
    new_balance = row["balance"] if isinstance(row, dict) else row[0]
    conn.commit()
    cursor.close()
    conn.close()

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

@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    user = get_current_user()
    if not user:
        flash("Bakiye yüklemek için lütfen önce giriş yapın!", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        card_holder = request.form.get("card_holder", "").strip()
        card_number = request.form.get("card_number", "").strip()
        exp_date = request.form.get("exp_date", "").strip()
        cvv = request.form.get("cvv", "").strip()
        amount = request.form.get("amount", "").strip()

        # 1. Tutar Denetimi
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash("Lütfen geçerli bir yükleme tutarı giriniz!", "danger")
                return redirect(url_for("deposit"))
        except ValueError:
            flash("Geçersiz bakiye tutarı formatı!", "danger")
            return redirect(url_for("deposit"))

        # 2. Banka Standartlarında Kart Denetimi
        is_valid, err_msg, bank_name, card_brand = validate_credit_card(card_holder, card_number, exp_date, cvv)
        if not is_valid:
            flash(f"❌ {err_msg}", "danger")
            return redirect(url_for("deposit"))

        # 3. 3D Secure Doğrulama Oturumu
        clean_num = re.sub(r"\D", "", card_number)
        test_sms_code = str(random.randint(100000, 999999))
        session["pending_payment"] = {
            "amount": amount_val,
            "bank_name": bank_name,
            "card_brand": card_brand,
            "card_last4": clean_num[-4:],
            "sms_code": test_sms_code,
            "created_at": datetime.datetime.now().strftime("%H:%M:%S")
        }

        return redirect(url_for("secure_3d"))

    balance = float(user["balance"] or 0.0)
    return render_template("deposit.html", balance=balance, username=user["username"])

@app.route("/3d-secure", methods=["GET", "POST"])
def secure_3d():
    user = get_current_user()
    payment = session.get("pending_payment")

    if not user or not payment:
        flash("Aktif bir ödeme oturumu bulunamadı.", "warning")
        return redirect(url_for("deposit"))

    if request.method == "POST":
        input_code = request.form.get("sms_code", "").strip()

        if input_code == payment["sms_code"]:
            amount_val = payment["amount"]

            conn = get_db()
            cursor = conn.cursor()
            p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
            cursor.execute(f"UPDATE users SET balance = balance + {p} WHERE id = {p}", (amount_val, user["id"]))
            cursor.execute(f"SELECT balance FROM users WHERE id = {p}", (user["id"],))
            row = cursor.fetchone()
            new_balance = row["balance"] if isinstance(row, dict) else row[0]
            conn.commit()
            cursor.close()
            conn.close()

            trx_id = f"TRX{random.randint(100000, 999999)}"
            send_discord_log(
                title="💳 3D Secure Doğrulanmış Ödeme Alındı",
                description=(
                    f"**Kullanıcı:** `{user['username']}`\n"
                    f"**Banka:** `{payment.get('bank_name', 'Banka')}`\n"
                    f"**Kart:** `**** **** **** {payment['card_last4']}` ({payment.get('card_brand', 'Kart')})\n"
                    f"**İşlem ID:** `{trx_id}`\n"
                    f"**Yüklenen Tutar:** {amount_val:.2f} TL\n"
                    f"**Güncel Bakiye:** {new_balance:.2f} TL"
                ),
                color=3066993
            )

            session.pop("pending_payment", None)
            flash(f"🎉 3D Secure doğrulaması başarılı! {amount_val:.2f} TL bakiyenize yüklendi.", "success")
            return redirect(url_for("home"))
        else:
            flash("❌ Hatalı SMS onay kodu! Lütfen telefonunuza iletilen kodu doğru girin.", "danger")
            return redirect(url_for("secure_3d"))

    return render_template("3d_secure.html", payment=payment)

@app.route("/buy/<int:product_id>", methods=["POST"])
def buy(product_id):
    user = get_current_user()
    if not user:
        flash("Satın alma işlemi yapabilmek için lütfen giriş yapın!", "warning")
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"SELECT * FROM products WHERE id = {p}", (product_id,))
    product = cursor.fetchone()
    
    if not product or product["stock"] <= 0:
        cursor.close()
        conn.close()
        flash("Ürün stokta kalmadı!", "danger")
        return redirect(url_for("home"))

    user_balance = float(user["balance"] or 0.0)
    if user_balance < product["price"]:
        cursor.close()
        conn.close()
        flash("Yetersiz bakiye! Lütfen önce bakiye yükleyin.", "danger")
        return redirect(url_for("home"))

    raw_prefix = "".join([c for c in product["title"][:4] if c.isalnum()]).upper()
    prefix = raw_prefix if raw_prefix else "EPIN"
    part1 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
    part2 = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=4))
    delivered_code = f"{prefix}-{part1}-{part2}"

    cursor.execute(f"UPDATE users SET balance = balance - {p} WHERE id = {p}", (product["price"], user["id"]))
    cursor.execute(f"UPDATE products SET stock = stock - 1 WHERE id = {p}", (product_id,))
    
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute(f"INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES ({p}, {p}, {p}, {p}, {p})",
                   (user["id"], product["title"], product["price"], delivered_code, now))
    
    cursor.execute(f"SELECT stock FROM products WHERE id = {p}", (product_id,))
    stock_row = cursor.fetchone()
    remaining_stock = stock_row["stock"] if isinstance(stock_row, dict) else stock_row[0]
    
    cursor.execute(f"SELECT balance FROM users WHERE id = {p}", (user["id"],))
    bal_row = cursor.fetchone()
    new_balance = bal_row["balance"] if isinstance(bal_row, dict) else bal_row[0]
    
    conn.commit()
    cursor.close()
    conn.close()

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

@app.route("/orders")
def orders():
    user = get_current_user()
    if not user:
        flash("Sipariş geçmişinizi görmek için lütfen giriş yapın!", "warning")
        return redirect(url_for("login"))

    balance = float(user["balance"] or 0.0)
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"SELECT * FROM orders WHERE user_id = {p} ORDER BY id DESC", (user["id"],))
    order_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template("orders.html", balance=balance, username=user["username"], orders=order_list)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
