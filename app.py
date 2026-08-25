from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
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

# --- TEK ANA SÜPER YÖNETİCİ ---
SUPER_ADMIN_USERNAME = "Lvbelc5baba"

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
                    balance REAL DEFAULT 0.0,
                    is_admin INTEGER DEFAULT 0
                );
            ''')
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin INTEGER DEFAULT 0;")
                conn.commit()
            except Exception:
                pass

            cursor.execute("UPDATE users SET is_admin = 1 WHERE username = %s;", (SUPER_ADMIN_USERNAME,))

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
            # Şifre Sıfırlama Talepleri Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reset_requests (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'Bekliyor',
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
                    balance REAL DEFAULT 0.0,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                conn.commit()
            except Exception:
                pass

            cursor.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (SUPER_ADMIN_USERNAME,))

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
            # Şifre Sıfırlama Talepleri Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reset_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'Bekliyor',
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Bu sayfayı görüntülemek için lütfen önce giriş yapın!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        is_super = (user and user["username"] == SUPER_ADMIN_USERNAME)
        is_adm = (user and bool(user.get("is_admin")))
        if not (is_super or is_adm):
            flash("⛔ Yetkisiz Erişim: Bu alana yalnızca yöneticiler erişebilir!", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated_function

# --- BANKA VE POS STANDARTLARINDA KART DOĞRULAMA ---
TURKISH_BINS = {
    "454671": ("Ziraat Bankası", "Visa"),
    "542374": ("Ziraat Bankası", "Mastercard"),
    "979201": ("Ziraat Bankası", "Troy"),
    "454359": ("Türkiye İş Bankası", "Visa"),
    "454360": ("Türkiye İş Bankası", "Visa"),
    "589283": ("Türkiye İş Bankası", "Mastercard"),
    "540036": ("Garanti BBVA", "Mastercard"),
    "517041": ("Garanti BBVA", "Mastercard"),
    "554960": ("Garanti BBVA", "Mastercard"),
    "405040": ("Garanti BBVA", "Visa"),
    "552608": ("Akbank", "Mastercard"),
    "589004": ("Akbank", "Mastercard"),
    "435509": ("Akbank", "Visa"),
    "979207": ("Akbank", "Troy"),
    "545103": ("Yapı Kredi", "Mastercard"),
    "516888": ("Yapı Kredi", "Mastercard"),
    "450634": ("Yapı Kredi", "Visa"),
    "491005": ("VakıfBank", "Visa"),
    "415792": ("VakıfBank", "Visa"),
    "542119": ("VakıfBank", "Mastercard"),
    "979288": ("VakıfBank", "Troy"),
    "531157": ("QNB Finansbank", "Mastercard"),
    "498749": ("QNB Finansbank", "Visa"),
    "415565": ("QNB Finansbank", "Visa"),
    "447505": ("Halkbank", "Visa"),
    "552879": ("Halkbank", "Mastercard"),
    "453144": ("Halkbank", "Visa"),
    "460345": ("DenizBank", "Visa"),
    "476662": ("DenizBank", "Visa"),
    "520019": ("DenizBank", "Mastercard"),
    "404809": ("Papara Card", "Mastercard"),
    "543719": ("Paycell", "Mastercard"),
    "516741": ("Tosla", "Mastercard"),
    "454314": ("İninal", "Visa")
}

def validate_credit_card(card_holder, card_number, exp_date, cvv):
    names = [n for n in card_holder.strip().split() if len(n) >= 2]
    if len(names) < 2:
        return False, "Kart üzerindeki isim ve soyisim eksiksiz girilmelidir.", None, None

    clean_num = re.sub(r"\D", "", card_number)
    if len(clean_num) != 16:
        return False, "Kredi kartı numarası tam olarak 16 haneli olmalıdır.", None, None

    bin_code = clean_num[:6]
    bank_info = TURKISH_BINS.get(bin_code)
    
    if not bank_info:
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

    exp_clean = exp_date.strip().replace(" ", "")
    if not re.match(r"^(0[1-9]|1[0-2])\/?([0-9]{2})$", exp_clean):
        return False, "Son kullanma tarihi geçersiz formatta! (Örn: 12/28)", None, None

    parts = exp_clean.split("/") if "/" in exp_clean else [exp_clean[:2], exp_clean[2:]]
    month, year = int(parts[0]), int(f"20{parts[1]}")
    
    now = datetime.datetime.now()
    if year < now.year or (year == now.year and month < now.month):
        return False, "Kartınızın son kullanma tarihi dolmuştur.", None, None

    if not (cvv.isdigit() and len(cvv) == 3):
        return False, "CVV güvenlik kodu 3 haneli sayı olmalıdır.", None, None

    return True, "Geçerli", bank_name, card_brand

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

# --- GENEL SAYFA ROTALARI ---

@app.route("/")
def home():
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
        
    return render_template("index.html", balance=balance, username=username, is_admin=is_admin, products=products)

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
            is_adm = 1 if username == SUPER_ADMIN_USERNAME else 0
            cursor.execute(f"INSERT INTO users (username, password, balance, is_admin) VALUES ({p}, {p}, 0.0, {p})", 
                           (username, hashed_pw, is_adm))
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

# --- ŞİFRE SIFIRLAMA TALEBİ SAYFASI ---
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()

        if not username or not email:
            flash("Kullanıcı adı ve iletişim e-posta adresi zorunludur!", "danger")
            return redirect(url_for("forgot_password"))

        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        
        # Kullanıcının varlığını kontrol et
        cursor.execute(f"SELECT id FROM users WHERE username = {p}", (username,))
        user_exists = cursor.fetchone()

        if not user_exists:
            cursor.close()
            conn.close()
            flash("Bu kullanıcı adına sahip bir hesap bulunamadı!", "danger")
            return redirect(url_for("forgot_password"))

        # Talebi kaydet
        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute(f"INSERT INTO reset_requests (username, email, status, created_at) VALUES ({p}, {p}, 'Bekliyor', {p})",
                       (username, email, now))
        conn.commit()
        cursor.close()
        conn.close()

        # Discord Bildirimi
        send_discord_log(
            title="📩 Yeni Şifre Sıfırlama Talebi",
            description=(
                f"**Kullanıcı:** `{username}`\n"
                f"**İletişim E-Posta:** `{email}`\n"
                f"**Tarih:** {now}\n"
                f"Yönetici panelinden şifresini güncelleyebilirsiniz."
            ),
            color=16753920
        )

        flash("✅ Şifre sıfırlama talebiniz yöneticiye iletildi. En kısa sürede e-postanız üzerinden sizinle iletişime geçilecektir.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Hesaptan çıkış yapıldı.", "info")
    return redirect(url_for("login"))

@app.route("/wheel")
@login_required
def wheel():
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))
    return render_template("wheel.html", balance=balance, username=username, is_admin=is_admin)

@app.route("/spin", methods=["POST"])
@login_required
def spin():
    user = get_current_user()
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
@login_required
def deposit():
    user = get_current_user()

    if request.method == "POST":
        card_holder = request.form.get("card_holder", "").strip()
        card_number = request.form.get("card_number", "").strip()
        exp_date = request.form.get("exp_date", "").strip()
        cvv = request.form.get("cvv", "").strip()
        amount = request.form.get("amount", "").strip()

        try:
            amount_val = float(amount)
            if amount_val <= 0:
                flash("Lütfen geçerli bir yükleme tutarı giriniz!", "danger")
                return redirect(url_for("deposit"))
        except ValueError:
            flash("Geçersiz bakiye tutarı formatı!", "danger")
            return redirect(url_for("deposit"))

        is_valid, err_msg, bank_name, card_brand = validate_credit_card(card_holder, card_number, exp_date, cvv)
        if not is_valid:
            flash(f"❌ {err_msg}", "danger")
            return redirect(url_for("deposit"))

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

        clean_num = re.sub(r"\D", "", card_number)
        trx_id = f"TRX{random.randint(100000, 999999)}"
        send_discord_log(
            title="💳 Bakiye Yüklendi",
            description=(
                f"**Kullanıcı:** `{user['username']}`\n"
                f"**Banka:** `{bank_name}`\n"
                f"**Kart:** `**** **** **** {clean_num[-4:]}` ({card_brand})\n"
                f"**İşlem ID:** `{trx_id}`\n"
                f"**Yüklenen:** {amount_val:.2f} TL\n"
                f"**Güncel Bakiye:** {new_balance:.2f} TL"
            ),
            color=3066993
        )

        flash(f"🎉 Ödeme onaylandı! {amount_val:.2f} TL bakiyenize başarıyla yüklendi.", "success")
        return redirect(url_for("home"))

    balance = float(user["balance"] or 0.0)
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))
    return render_template("deposit.html", balance=balance, username=user["username"], is_admin=is_admin)

@app.route("/buy/<int:product_id>", methods=["POST"])
@login_required
def buy(product_id):
    user = get_current_user()

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
@login_required
def orders():
    user = get_current_user()
    balance = float(user["balance"] or 0.0)
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))
    
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"SELECT * FROM orders WHERE user_id = {p} ORDER BY id DESC", (user["id"],))
    order_list = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template("orders.html", balance=balance, username=user["username"], is_admin=is_admin, orders=order_list)

# --- SÜPER ADMIN & YÖNETİCİ PANELİ ---

@app.route("/admin")
@admin_required
def admin_panel():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, balance, is_admin FROM users ORDER BY id DESC")
    all_users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM products ORDER BY id ASC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    all_orders = cursor.fetchall()

    # Bekleyen ve tamamlanan şifre talepleri
    cursor.execute("SELECT * FROM reset_requests ORDER BY id DESC")
    reset_reqs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    is_super = (user["username"] == SUPER_ADMIN_USERNAME)
    return render_template("admin.html", 
                           username=user["username"], 
                           is_super=is_super, 
                           super_admin_name=SUPER_ADMIN_USERNAME,
                           users=all_users, 
                           products=products, 
                           orders=all_orders,
                           reset_requests=reset_reqs)

# --- ŞİFRE SIFIRLAMA TALEBİNİ İŞLEME (YENİ ŞİFRE BELİRLEME) ---
@app.route("/admin/user/reset-password", methods=["POST"])
@admin_required
def admin_reset_user_password():
    target_username = request.form.get("username")
    new_password = request.form.get("new_password", "").strip()
    request_id = request.form.get("request_id")

    if not new_password:
        flash("Yeni şifre boş bırakılamaz!", "danger")
        return redirect(url_for("admin_panel"))

    hashed_pw = generate_password_hash(new_password)
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"

    cursor.execute(f"UPDATE users SET password = {p} WHERE username = {p}", (hashed_pw, target_username))
    if request_id:
        cursor.execute(f"UPDATE reset_requests SET status = 'Tamamlandı' WHERE id = {p}", (request_id,))
    
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"'{target_username}' kullanıcısının şifresi başarıyla güncellendi! Yeni şifre: {new_password}", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/user/toggle-admin/<int:user_id>", methods=["POST"])
@admin_required
def admin_toggle_role(user_id):
    current = get_current_user()
    
    if current["username"] != SUPER_ADMIN_USERNAME:
        flash("⛔ Admin yetkisi verme veya kaldırma yetkisi yalnızca Süper Admin'e (Lvbelc5baba) aittir!", "danger")
        return redirect(url_for("admin_panel"))

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    
    cursor.execute(f"SELECT is_admin, username FROM users WHERE id = {p}", (user_id,))
    target = cursor.fetchone()
    
    if target:
        if target["username"] == SUPER_ADMIN_USERNAME:
            flash("Ana Süper Yöneticinin yetkisi değiştirilemez!", "warning")
        else:
            new_role = 0 if target["is_admin"] else 1
            cursor.execute(f"UPDATE users SET is_admin = {p} WHERE id = {p}", (new_role, user_id))
            conn.commit()
            status_text = "Yönetici yapıldı 👑" if new_role == 1 else "Yöneticilik yetkisi alındı ❌"
            flash(f"'{target['username']}' kullanıcısı {status_text}.", "success")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_panel"))

@app.route("/admin/product/add", methods=["POST"])
@admin_required
def admin_add_product():
    title = request.form.get("title", "").strip()
    price = float(request.form.get("price", 0.0))
    image = request.form.get("image", "").strip()
    stock = int(request.form.get("stock", 100))

    if title and price > 0:
        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"INSERT INTO products (title, price, image, stock) VALUES ({p}, {p}, {p}, {p})",
                       (title, price, image, stock))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Yeni ürün başarıyla eklendi.", "success")
    else:
        flash("Ürün adı ve fiyatı zorunludur!", "danger")
    return redirect(url_for("admin_panel"))

@app.route("/admin/product/update/<int:product_id>", methods=["POST"])
@admin_required
def admin_update_product(product_id):
    price = float(request.form.get("price", 0.0))
    stock = int(request.form.get("stock", 0))

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"UPDATE products SET price = {p}, stock = {p} WHERE id = {p}", (price, stock, product_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Ürün fiyatı ve stoğu başarıyla güncellendi.", "success")
    return redirect(url_for("admin_panel"))

@app.route("/admin/product/delete/<int:product_id>", methods=["POST"])
@admin_required
def admin_delete_product(product_id):
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"DELETE FROM products WHERE id = {p}", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Ürün sistemden silindi.", "info")
    return redirect(url_for("admin_panel"))

@app.route("/admin/user/set-balance", methods=["POST"])
@admin_required
def admin_set_balance():
    user_id = request.form.get("user_id")
    new_balance = float(request.form.get("balance", 0.0))

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"UPDATE users SET balance = {p} WHERE id = {p}", (new_balance, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Kullanıcı bakiyesi başarıyla güncellendi.", "success")
    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
