from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import re
import json
import requests
import datetime
import random
import string
import sqlite3

app = Flask(__name__)
app.secret_key = "epin-super-gizli-anahtar-12345"

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "ico"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1525268830635429930/Lwnf7QQj43IMSHJDrGgj68YpQc0ZKLZ5BF_0nPNQYTMegtVC0ZqlTcfROtV5iZtTmw98"
DATABASE_URL = os.environ.get("DATABASE_URL")

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
                    stock INTEGER DEFAULT 234,
                    main_category TEXT DEFAULT 'oyun',
                    sub_category TEXT DEFAULT 'epin'
                );
            ''')
            try:
                cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS main_category TEXT DEFAULT 'oyun';")
                cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS sub_category TEXT DEFAULT 'epin';")
                conn.commit()
            except Exception:
                pass

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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reset_requests (
                    id SERIAL PRIMARY KEY,
                    username TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'Bekliyor',
                    created_at TEXT
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaways (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    reward TEXT,
                    image TEXT,
                    is_paid INTEGER DEFAULT 0,
                    ticket_price REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'Aktif',
                    winner_username TEXT,
                    delivered_code TEXT,
                    created_at TEXT
                );
            ''')
            try:
                cursor.execute("ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS is_paid INTEGER DEFAULT 0;")
                cursor.execute("ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS ticket_price REAL DEFAULT 0.0;")
                conn.commit()
            except Exception:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS site_settings (
                    id SERIAL PRIMARY KEY,
                    site_title TEXT DEFAULT 'EPIN & SMM PAZARI',
                    site_logo TEXT DEFAULT '',
                    font_family TEXT DEFAULT 'Orbitron',
                    logo_position TEXT DEFAULT 'left',
                    logo_height INTEGER DEFAULT 40,
                    font_size INTEGER DEFAULT 22,
                    text_color TEXT DEFAULT '#eab308',
                    letter_colors TEXT DEFAULT ''
                );
            ''')
            try:
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS font_family TEXT DEFAULT 'Orbitron';")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS logo_position TEXT DEFAULT 'left';")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS logo_height INTEGER DEFAULT 40;")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS font_size INTEGER DEFAULT 22;")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS text_color TEXT DEFAULT '#eab308';")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS letter_colors TEXT DEFAULT '';")
                conn.commit()
            except Exception:
                pass

            cursor.execute("SELECT id FROM site_settings LIMIT 1")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO site_settings (site_title, site_logo, font_family, logo_position, logo_height, font_size, text_color, letter_colors) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
                               ('EPIN & SMM PAZARI', '', 'Orbitron', 'left', 40, 22, '#eab308', '[]'))
            conn.commit()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaway_participants (
                    id SERIAL PRIMARY KEY,
                    giveaway_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    joined_at TEXT
                );
            ''')
            conn.commit()

            varsayilan_urunler = [
                ("Valorant 1200 VP", 150.0, "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", 234, "oyun", "valorant"),
                ("PUBG Mobile 660 UC", 210.0, "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", 234, "oyun", "pubg"),
                ("Steam 10 USD Cüzdan", 320.0, "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", 234, "oyun", "steam"),
                ("Instagram 1.000 Türk Takipçi", 45.0, "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", 500, "sosyal", "instagram"),
                ("Instagram 5.000 Beğeni Paketi", 35.0, "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", 500, "sosyal", "instagram"),
                ("TikTok 10.000 İzlenme & Beğeni", 40.0, "https://images.unsplash.com/photo-1596558450255-7c0b7be9d56a?w=400", 500, "sosyal", "tiktok"),
                ("YouTube 1.000 Abone & 4.000 Saat", 180.0, "https://images.unsplash.com/photo-1543269865-cbf427effbad?w=400", 200, "sosyal", "youtube")
            ]
            for title, price, img, stock, main_cat, sub_cat in varsayilan_urunler:
                cursor.execute("SELECT id FROM products WHERE title = %s", (title,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO products (title, price, image, stock, main_category, sub_category) VALUES (%s, %s, %s, %s, %s, %s)", 
                                   (title, price, img, stock, main_cat, sub_cat))
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
                    stock INTEGER DEFAULT 234,
                    main_category TEXT DEFAULT 'oyun',
                    sub_category TEXT DEFAULT 'epin'
                )
            ''')
            try:
                cursor.execute("ALTER TABLE products ADD COLUMN main_category TEXT DEFAULT 'oyun'")
                cursor.execute("ALTER TABLE products ADD COLUMN sub_category TEXT DEFAULT 'epin'")
                conn.commit()
            except Exception:
                pass

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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reset_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'Bekliyor',
                    created_at TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    reward TEXT,
                    image TEXT,
                    is_paid INTEGER DEFAULT 0,
                    ticket_price REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'Aktif',
                    winner_username TEXT,
                    delivered_code TEXT,
                    created_at TEXT
                )
            ''')
            try:
                cursor.execute("ALTER TABLE giveaways ADD COLUMN is_paid INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE giveaways ADD COLUMN ticket_price REAL DEFAULT 0.0")
                conn.commit()
            except Exception:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS site_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_title TEXT DEFAULT 'EPIN & SMM PAZARI',
                    site_logo TEXT DEFAULT '',
                    font_family TEXT DEFAULT 'Orbitron',
                    logo_position TEXT DEFAULT 'left',
                    logo_height INTEGER DEFAULT 40,
                    font_size INTEGER DEFAULT 22,
                    text_color TEXT DEFAULT '#eab308',
                    letter_colors TEXT DEFAULT ''
                )
            ''')
            try:
                cursor.execute("ALTER TABLE site_settings ADD COLUMN font_family TEXT DEFAULT 'Orbitron'")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN logo_position TEXT DEFAULT 'left'")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN logo_height INTEGER DEFAULT 40")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN font_size INTEGER DEFAULT 22")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN text_color TEXT DEFAULT '#eab308'")
                cursor.execute("ALTER TABLE site_settings ADD COLUMN letter_colors TEXT DEFAULT ''")
                conn.commit()
            except Exception:
                pass

            cursor.execute("SELECT id FROM site_settings LIMIT 1")
            if not cursor.fetchone():
                cursor.execute("INSERT INTO site_settings (site_title, site_logo, font_family, logo_position, logo_height, font_size, text_color, letter_colors) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                               ('EPIN & SMM PAZARI', '', 'Orbitron', 'left', 40, 22, '#eab308', '[]'))
            conn.commit()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS giveaway_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    joined_at TEXT
                )
            ''')
            conn.commit()

            varsayilan_urunler = [
                ("Valorant 1200 VP", 150.0, "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", 234, "oyun", "valorant"),
                ("PUBG Mobile 660 UC", 210.0, "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", 234, "oyun", "pubg"),
                ("Steam 10 USD Cüzdan", 320.0, "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", 234, "oyun", "steam"),
                ("Instagram 1.000 Türk Takipçi", 45.0, "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", 500, "sosyal", "instagram"),
                ("Instagram 5.000 Beğeni Paketi", 35.0, "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", 500, "sosyal", "instagram"),
                ("TikTok 10.000 İzlenme & Beğeni", 40.0, "https://images.unsplash.com/photo-1596558450255-7c0b7be9d56a?w=400", 500, "sosyal", "tiktok"),
                ("YouTube 1.000 Abone & 4.000 Saat", 180.0, "https://images.unsplash.com/photo-1543269865-cbf427effbad?w=400", 200, "sosyal", "youtube")
            ]
            for title, price, img, stock, main_cat, sub_cat in varsayilan_urunler:
                cursor.execute("SELECT id FROM products WHERE title = ?", (title,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("INSERT INTO products (title, price, image, stock, main_category, sub_category) VALUES (?, ?, ?, ?, ?, ?)", 
                                   (title, price, img, stock, main_cat, sub_cat))
            conn.commit()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Veritabanı başlatma hatası: {e}")

init_db()

# --- SİTE AYARLARINI GETİRME ---
def get_site_settings():
    default_settings = {
        "title": "EPIN & SMM PAZARI",
        "logo": "",
        "font_family": "Orbitron",
        "logo_position": "left",
        "logo_height": 40,
        "font_size": 22,
        "text_color": "#eab308",
        "letter_colors": "[]",
        "formatted_letters": []
    }
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM site_settings ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            if isinstance(row, dict):
                title = row.get("site_title") or default_settings["title"]
                raw_colors = row.get("letter_colors") or "[]"
                base_color = row.get("text_color") or "#eab308"
                settings_data = {
                    "title": title,
                    "logo": row.get("site_logo") or "",
                    "font_family": row.get("font_family") or "Orbitron",
                    "logo_position": row.get("logo_position") or "left",
                    "logo_height": row.get("logo_height") or 40,
                    "font_size": row.get("font_size") or 22,
                    "text_color": base_color,
                    "letter_colors": raw_colors
                }
            else:
                title = row[1] or default_settings["title"]
                raw_colors = row[8] if len(row) > 8 and row[8] else "[]"
                base_color = row[7] if len(row) > 7 and row[7] else "#eab308"
                settings_data = {
                    "title": title,
                    "logo": row[2] or "",
                    "font_family": row[3] if len(row) > 3 and row[3] else "Orbitron",
                    "logo_position": row[4] if len(row) > 4 and row[4] else "left",
                    "logo_height": row[5] if len(row) > 5 and row[5] else 40,
                    "font_size": row[6] if len(row) > 6 and row[6] else 22,
                    "text_color": base_color,
                    "letter_colors": raw_colors
                }

            try:
                color_list = json.loads(settings_data["letter_colors"])
            except Exception:
                color_list = []

            formatted = []
            for i, char in enumerate(settings_data["title"]):
                c = color_list[i] if i < len(color_list) and color_list[i] else settings_data["text_color"]
                formatted.append({"char": char, "color": c})

            settings_data["formatted_letters"] = formatted
            return settings_data
    except Exception as e:
        print(f"Site ayarları getirme hatası: {e}")
    
    default_settings["formatted_letters"] = [{"char": c, "color": "#eab308"} for c in default_settings["title"]]
    return default_settings

# --- KOD ÜRETİM MOTORU ---
def generate_game_code(product_title):
    title_lower = product_title.lower()
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    
    if "valorant" in title_lower or "vp" in title_lower:
        p1 = "".join(random.choices(chars, k=4))
        p2 = "".join(random.choices(chars, k=4))
        p3 = "".join(random.choices(chars, k=4))
        return f"RA-{p1}-{p2}-{p3}"
    elif "pubg" in title_lower or "uc" in title_lower:
        return "".join(random.choices(chars, k=14))
    elif "steam" in title_lower or "usd" in title_lower:
        p1 = "".join(random.choices(chars, k=5))
        p2 = "".join(random.choices(chars, k=5))
        p3 = "".join(random.choices(chars, k=5))
        return f"{p1}-{p2}-{p3}"
    elif any(k in title_lower for k in ["takipçi", "beğeni", "izlenme", "instagram", "tiktok", "youtube", "twitter"]):
        p1 = "".join(random.choices(chars, k=4))
        p2 = "".join(random.choices(chars, k=4))
        return f"SMM-KEY-{p1}-{p2}"
    else:
        p1 = "".join(random.choices(chars, k=4))
        p2 = "".join(random.choices(chars, k=4))
        return f"EPIN-{p1}-{p2}"

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

# --- BANKA VE POS KART DOĞRULAMA ---
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

# --- CANLI DESTEK ---
SUPPORT_AGENTS = {
    "erkek": ["Ahmet K.", "Murat Y.", "Emre T.", "Can B.", "Burak D.", "Kaan S."],
    "kadin": ["Elif S.", "Zeynep T.", "Ayşe M.", "Seda B.", "Merve K.", "Gizem A."]
}

@app.route("/api/support/start", methods=["POST"])
def support_start():
    data = request.get_json() or {}
    topic = data.get("topic", "genel")
    last_gender = session.get("last_agent_gender", None)

    if last_gender:
        if random.random() < 0.25:
            current_gender = last_gender
        else:
            current_gender = "kadin" if last_gender == "erkek" else "erkek"
    else:
        current_gender = random.choice(["erkek", "kadin"])

    session["last_agent_gender"] = current_gender
    agent_name = random.choice(SUPPORT_AGENTS[current_gender])

    department_names = {
        "odeme": "Bakiye & Finans Uzmanı",
        "epin": "E-Pin & Kod Teslimat Uzmanı",
        "sosyal": "Sosyal Medya Hizmetleri Uzmanı",
        "teknik": "Teknik Destek Uzmanı"
    }
    dept = department_names.get(topic, "Müşteri Temsilcisi")

    welcome_messages = {
        "odeme": f"Merhaba! Ben {agent_name}, Finans ve Bakiye departmanındanım. Ödeme veya bakiye yükleme işleminizle ilgili nasıl yardımcı olabilirim?",
        "epin": f"Merhaba! Ben {agent_name}, Kod ve Teslimat birimindenim. Satın aldığınız e-pin veya oyun koduyla ilgili detayları paylaşabilir misiniz?",
        "sosyal": f"Merhaba! Ben {agent_name}, Sosyal Medya Hizmetleri uzmanıyım. Takipçi, beğeni veya izlenme siparişinizle ilgili yardımcı olmaktan memnuniyet duyarım.",
        "teknik": f"Merhaba! Ben {agent_name}, Teknik Destek ekibindenim. Sitede karşılaştığınız teknik sorunu detaylandırır mısınız?"
    }

    return jsonify({
        "success": True,
        "agent_name": agent_name,
        "department": dept,
        "gender": current_gender,
        "initial_message": welcome_messages.get(topic, f"Merhaba! Ben {agent_name}, size nasıl yardımcı olabilirim?")
    })

@app.route("/api/support/message", methods=["POST"])
def support_message():
    data = request.get_json() or {}
    user_msg = data.get("message", "").lower()
    topic = data.get("topic", "genel")

    if any(k in user_msg for k in ["bakiye", "yükle", "kart", "para", "ödeme", "pos"]):
        reply = "Bakiye yükleme işlemleriniz 3D Secure onayının ardından anında hesabınıza yansımaktadır. Herhangi bir gecikme durumunda işlem ID numaranızı kontrol edebilirim."
    elif any(k in user_msg for k in ["kod", "gelmedi", "çalışmıyor", "hatalı", "vp", "uc", "steam"]):
        reply = "Tüm kodlar sistemimizde anlık ve lisanslı olarak üretilmektedir. 'Siparişlerim' sekmesinden teslim edilen kodu kopyalayıp ilgili platformda aktifleştirebilirsiniz."
    elif any(k in user_msg for k in ["takipçi", "beğeni", "izlenme", "tiktok", "instagram", "düşüş"]):
        reply = "Sosyal medya siparişleri sıraya alınarak 5-15 dakika içinde organik olarak gönderilmeye başlar. Profilinizin gizli (özel) olmadığından emin olunuz."
    elif any(k in user_msg for k in ["çekiliş", "kazanan", "giveaway", "ödül", "bilet"]):
        reply = "Aktif çekilişlerimize 'Çekilişler' sayfasından ücretsiz veya ücretli katılabilirsiniz!"
    elif any(k in user_msg for k in ["admin", "yetki", "berat", "lvbelc5baba", "şifre"]):
        reply = "Yönetici ve hesap güvenliği işlemleriniz kayıt altına alınmıştır. Şifre sıfırlama taleplerini 'Şifremi Unuttum' ekranından iletebilirsiniz."
    elif any(k in user_msg for k in ["merhaba", "selam", "sa", "günaydın", "iyi günler"]):
        reply = "Tekrar merhaba! Sorununuzu çözebilmemiz için detayları iletmeniz yeterlidir."
    else:
        reply = "Konuyu anladım, sistem kayıtlarımızı ve sipariş veritabanını inceliyorum. Lütfen hatta kalınız."

    return jsonify({
        "success": True,
        "reply": reply
    })

# --- GENEL SAYFA ROTALARI ---

@app.route("/")
def home():
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))
    settings = get_site_settings()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    cursor.close()
    conn.close()
        
    return render_template("index.html", balance=balance, username=username, is_admin=is_admin, products=products, settings=settings)

# --- ÇEKİLİŞ SAYFASI & KATILMA ---
@app.route("/giveaways")
def giveaways():
    user = get_current_user()
    balance = float(user["balance"]) if user and user["balance"] is not None else 0.0
    username = user["username"] if user else None
    is_admin = bool(user and (user["username"] == SUPER_ADMIN_USERNAME or bool(user.get("is_admin"))))
    settings = get_site_settings()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM giveaways ORDER BY id DESC")
    all_giveaways = cursor.fetchall()

    joined_ids = []
    if user:
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"SELECT giveaway_id FROM giveaway_participants WHERE user_id = {p}", (user["id"],))
        joined_rows = cursor.fetchall()
        joined_ids = [r["giveaway_id"] if isinstance(r, dict) else r[0] for r in joined_rows]

    giveaway_list = []
    for g in all_giveaways:
        g_dict = dict(g)
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"SELECT COUNT(*) FROM giveaway_participants WHERE giveaway_id = {p}", (g_dict["id"],))
        count_row = cursor.fetchone()
        g_dict["participant_count"] = count_row[0] if not isinstance(count_row, dict) else list(count_row.values())[0]
        g_dict["is_joined"] = g_dict["id"] in joined_ids
        giveaway_list.append(g_dict)

    cursor.close()
    conn.close()

    return render_template("giveaways.html", balance=balance, username=username, is_admin=is_admin, giveaways=giveaway_list, settings=settings)

@app.route("/giveaways/join/<int:giveaway_id>", methods=["POST"])
@login_required
def join_giveaway(giveaway_id):
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"

    cursor.execute(f"SELECT * FROM giveaways WHERE id = {p}", (giveaway_id,))
    gw = cursor.fetchone()
    if not gw or gw["status"] != "Aktif":
        cursor.close()
        conn.close()
        flash("Bu çekiliş sona ermiş veya aktif değil!", "danger")
        return redirect(url_for("giveaways"))

    cursor.execute(f"SELECT id FROM giveaway_participants WHERE giveaway_id = {p} AND user_id = {p}", (giveaway_id, user["id"]))
    already_joined = cursor.fetchone()
    if already_joined:
        cursor.close()
        conn.close()
        flash("Bu çekilişe zaten katıldınız!", "warning")
        return redirect(url_for("giveaways"))

    is_paid = bool(gw["is_paid"])
    ticket_price = float(gw["ticket_price"] or 0.0)

    if is_paid and ticket_price > 0:
        current_balance = float(user["balance"] or 0.0)
        if current_balance < ticket_price:
            cursor.close()
            conn.close()
            flash(f"Yetersiz bakiye! Bu çekilişe katılmak için {ticket_price:.2f} TL gerekiyor.", "danger")
            return redirect(url_for("giveaways"))
        
        cursor.execute(f"UPDATE users SET balance = balance - {p} WHERE id = {p}", (ticket_price, user["id"]))

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute(f"INSERT INTO giveaway_participants (giveaway_id, user_id, username, joined_at) VALUES ({p}, {p}, {p}, {p})",
                   (giveaway_id, user["id"], user["username"], now))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"🎉 '{gw['title']}' çekilişine başarıyla katıldınız!", "success")
    return redirect(url_for("giveaways"))

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

    return render_template("register.html", settings=get_site_settings())

@app.route("/login", methods=["GET", "POST"])
def login():
    user = get_current_user()
    if user:
        return redirect(url_for("home"))

    failed_attempts = session.get("failed_attempts", 0)

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
            failed_attempts += 1
            session["failed_attempts"] = failed_attempts
            
            if failed_attempts >= 3:
                flash(f"⚠️ {failed_attempts} defa hatalı giriş yaptınız! Şifrenizi unuttuysanız aşağıdaki alandan sıfırlama talebinde bulunabilirsiniz.", "warning")
            else:
                flash("Kullanıcı adı veya şifre hatalı!", "danger")
            return redirect(url_for("login"))

    return render_template("login.html", failed_attempts=failed_attempts, settings=get_site_settings())

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
        
        cursor.execute(f"SELECT id FROM users WHERE username = {p}", (username,))
        user_exists = cursor.fetchone()

        if not user_exists:
            cursor.close()
            conn.close()
            flash("Bu kullanıcı adına sahip bir hesap bulunamadı!", "danger")
            return redirect(url_for("forgot_password"))

        now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute(f"INSERT INTO reset_requests (username, email, status, created_at) VALUES ({p}, {p}, 'Bekliyor', {p})",
                       (username, email, now))
        conn.commit()
        cursor.close()
        conn.close()

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

        session["failed_attempts"] = 0
        flash("✅ Şifre sıfırlama talebiniz yöneticiye iletildi. En kısa sürede e-postanız üzerinden sizinle iletişime geçilecektir.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html", settings=get_site_settings())

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
    return render_template("wheel.html", balance=balance, username=username, is_admin=is_admin, settings=get_site_settings())

@app.route("/spin", methods=["POST"])
@login_required
def spin():
    user = get_current_user()
    data = request.get_json() or {}
    tier = data.get("tier", "bronze")
    is_simulation = bool(data.get("simulation", False))
    
    tier_costs = {"bronze": 50.0, "silver": 150.0, "gold": 300.0}
    cost = tier_costs.get(tier, 50.0)

    current_balance = float(user["balance"] or 0.0)
    if not is_simulation and current_balance < cost:
        return jsonify({"success": False, "error": "Yetersiz bakiye! Lütfen önce bakiye yükleyin veya Deneme Modunu kullanın."}), 400

    if tier == "gold":
        options = [
            {"reward": "10$ Steam USD", "label": "Steam 10 USD Cüzdan Kodu"},
            {"reward": "660 PUBG UC", "label": "PUBG Mobile 660 UC"},
            {"reward": "25$ Steam USD", "label": "Steam 25 USD Cüzdan Kodu"},
            {"reward": "2480 VP", "label": "2480 Valorant Points"},
            {"reward": "1800 PUBG UC", "label": "PUBG Mobile 1800 UC"},
            {"reward": "50$ Steam USD", "label": "Steam 50 USD Cüzdan Kodu (Nadir)"},
            {"reward": "5350 VP", "label": "5350 Valorant Points"},
            {"reward": "3850 PUBG UC", "label": "PUBG Mobile 3850 UC"},
            {"reward": "100$ Steam USD", "label": "Steam 100 USD Cüzdan Kodu (BÜYÜK ÖDÜL)"},
            {"reward": "8100 PUBG UC", "label": "PUBG Mobile 8100 UC (BÜYÜK ÖDÜL)"},
            {"reward": "11000 VP", "label": "11000 Valorant Points (BÜYÜK ÖDÜL)"}
        ]
        weights = [25, 20, 15, 12, 10, 6, 5, 4, 1.5, 1, 0.5]
    elif tier == "silver":
        options = [
            {"reward": "5$ Steam USD", "label": "Steam 5 USD Cüzdan Kodu"},
            {"reward": "60 PUBG UC", "label": "PUBG Mobile 60 UC"},
            {"reward": "600 VP", "label": "600 Valorant Points"},
            {"reward": "10$ Steam USD", "label": "Steam 10 USD Cüzdan Kodu"},
            {"reward": "325 PUBG UC", "label": "PUBG Mobile 325 UC"},
            {"reward": "1200 VP", "label": "1200 Valorant Points"},
            {"reward": "20$ Steam USD", "label": "Steam 20 USD Cüzdan Kodu"},
            {"reward": "660 PUBG UC", "label": "PUBG Mobile 660 UC"},
            {"reward": "30$ Steam USD", "label": "Steam 30 USD Cüzdan Kodu (Büyük)"},
            {"reward": "2480 VP", "label": "2480 Valorant Points"}
        ]
        weights = [25, 20, 18, 12, 10, 7, 4, 2, 1.5, 0.5]
    else:
        options = [
            {"reward": "1$ Steam USD", "label": "Steam 1 USD Cüzdan Kodu"},
            {"reward": "150 VP", "label": "150 Valorant Points"},
            {"reward": "60 PUBG UC", "label": "PUBG Mobile 60 UC"},
            {"reward": "2.5$ Steam USD", "label": "Steam 2.5 USD Cüzdan Kodu"},
            {"reward": "600 VP", "label": "600 Valorant Points"},
            {"reward": "5$ Steam USD", "label": "Steam 5 USD Cüzdan Kodu"},
            {"reward": "325 PUBG UC", "label": "PUBG Mobile 325 UC"},
            {"reward": "10$ Steam USD", "label": "Steam 10 USD Cüzdan Kodu (Büyük)"},
            {"reward": "1200 VP", "label": "1200 Valorant Points"},
            {"reward": "660 PUBG UC", "label": "PUBG Mobile 660 UC"}
        ]
        weights = [30, 25, 18, 10, 8, 4, 2.5, 1.5, 0.7, 0.3]

    chosen = random.choices(options, weights=weights, k=1)[0]
    code = generate_game_code(chosen["label"])

    if is_simulation:
        return jsonify({
            "success": True,
            "simulation": True,
            "reward": chosen["reward"],
            "reward_label": chosen["label"],
            "code": "TEST-SIMULASYON-KODU",
            "new_balance": f"{current_balance:.2f}"
        })

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
            f"**Kazanılan:** 🎉 {chosen['reward']}\n"
            f"**Kod:** `{code}`\n"
            f"**Kalan Bakiye:** {new_balance:.2f} TL"
        ),
        color=15844367
    )

    return jsonify({
        "success": True,
        "simulation": False,
        "reward": chosen["reward"],
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
    return render_template("deposit.html", balance=balance, username=user["username"], is_admin=is_admin, settings=get_site_settings())

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

    delivered_code = generate_game_code(product["title"])

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
        title="🛒 Satın Alma Gerçekleşti",
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

    flash(f"🎉 Satın Alma Başarılı! Teslim Edilen Kodunuz: {delivered_code}", "success")
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
    
    return render_template("orders.html", balance=balance, username=user["username"], is_admin=is_admin, orders=order_list, settings=get_site_settings())

# --- SÜPER ADMIN & YÖNETİCİ PANELİ ---

@app.route("/admin")
@admin_required
def admin_panel():
    user = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, balance, is_admin FROM users ORDER BY id DESC")
    all_users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = cursor.fetchall()
    
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    all_orders = cursor.fetchall()

    cursor.execute("SELECT * FROM reset_requests ORDER BY id DESC")
    reset_reqs = cursor.fetchall()

    # Çekilişleri ve katılımcı listelerini çek
    cursor.execute("SELECT * FROM giveaways ORDER BY id DESC")
    raw_giveaways = cursor.fetchall()
    admin_giveaways = []
    for g in raw_giveaways:
        g_dict = dict(g)
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"SELECT id, username, joined_at FROM giveaway_participants WHERE giveaway_id = {p} ORDER BY id DESC", (g_dict["id"],))
        participants = cursor.fetchall()
        g_dict["participants"] = [dict(part) if isinstance(part, dict) else {"id": part[0], "username": part[1], "joined_at": part[2]} for part in participants]
        g_dict["participant_count"] = len(g_dict["participants"])
        admin_giveaways.append(g_dict)
    
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
                           reset_requests=reset_reqs,
                           giveaways=admin_giveaways,
                           settings=get_site_settings())

# --- SAYFA DÜZENLERİ & HARF RENKLERİ GÜNCELLEME ---
@app.route("/admin/settings/update", methods=["POST"])
@admin_required
def admin_update_settings():
    new_title = request.form.get("site_title", "").strip()
    font_family = request.form.get("font_family", "Orbitron").strip()
    logo_position = request.form.get("logo_position", "left").strip()
    logo_height = int(request.form.get("logo_height", 40))
    font_size = int(request.form.get("font_size", 22))
    text_color = request.form.get("text_color", "#eab308").strip()
    letter_colors = request.form.get("letter_colors", "[]").strip()

    if not new_title:
        flash("Site başlığı boş bırakılamaz!", "danger")
        return redirect(url_for("admin_panel"))

    logo_file = request.files.get("logo_file")
    logo_path = None

    if logo_file and logo_file.filename and allowed_file(logo_file.filename):
        ext = logo_file.filename.rsplit(".", 1)[1].lower()
        filename = f"logo_{int(datetime.datetime.now().timestamp())}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        logo_file.save(filepath)
        logo_path = f"/static/uploads/{filename}"

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"

    cursor.execute("SELECT id, site_logo FROM site_settings LIMIT 1")
    current_settings = cursor.fetchone()

    if current_settings:
        row_id = current_settings["id"] if isinstance(current_settings, dict) else current_settings[0]
        old_logo = current_settings["site_logo"] if isinstance(current_settings, dict) else current_settings[1]
        final_logo = logo_path if logo_path else (old_logo or "")
        cursor.execute(f'''
            UPDATE site_settings 
            SET site_title = {p}, site_logo = {p}, font_family = {p}, logo_position = {p}, logo_height = {p}, font_size = {p}, text_color = {p}, letter_colors = {p} 
            WHERE id = {p}
        ''', (new_title, final_logo, font_family, logo_position, logo_height, font_size, text_color, letter_colors, row_id))
    else:
        final_logo = logo_path if logo_path else ""
        cursor.execute(f'''
            INSERT INTO site_settings (site_title, site_logo, font_family, logo_position, logo_height, font_size, text_color, letter_colors) 
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        ''', (new_title, final_logo, font_family, logo_position, logo_height, font_size, text_color, letter_colors))

    conn.commit()
    cursor.close()
    conn.close()

    flash("🎨 Sayfa düzenleri ve logo ayarları başarıyla kaydedildi!", "success")
    return redirect(url_for("admin_panel"))

# --- ADMIN: ÇEKİLİŞ EKLEME ---
@app.route("/admin/giveaway/add", methods=["POST"])
@admin_required
def admin_add_giveaway():
    title = request.form.get("title", "").strip()
    reward = request.form.get("reward", "").strip()
    image = request.form.get("image", "").strip()
    is_paid = 1 if request.form.get("is_paid") == "1" else 0
    ticket_price = float(request.form.get("ticket_price", 0.0)) if is_paid else 0.0

    if not title or not reward:
        flash("Çekiliş başlığı ve ödül adı zorunludur!", "danger")
        return redirect(url_for("admin_panel"))

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"INSERT INTO giveaways (title, reward, image, is_paid, ticket_price, status, created_at) VALUES ({p}, {p}, {p}, {p}, {p}, 'Aktif', {p})",
                   (title, reward, image, is_paid, ticket_price, now))
    conn.commit()
    cursor.close()
    conn.close()

    type_text = f"Ücretli ({ticket_price:.2f} TL)" if is_paid else "Ücretsiz"
    send_discord_log(
        title="🎁 Yeni Çekiliş Başlatıldı!",
        description=f"**Başlık:** {title}\n**Ödül:** {reward}\n**Tür:** {type_text}",
        color=3066993
    )

    flash("Yeni çekiliş başarıyla yayınlandı.", "success")
    return redirect(url_for("admin_panel"))

# --- ADMIN: ÇEKİLİŞE RASTGELE KATILIMCI EKLEME ---
@app.route("/admin/giveaway/add-random-participant/<int:giveaway_id>", methods=["POST"])
@admin_required
def admin_add_random_participant(giveaway_id):
    fake_names = ["emir_pro", "berkay99", "caner_val", "zeynep_x", "furkan_pubg", "ali_kaya", "selin_t", "burak_34", "melisa_g", "kerem_77"]
    random_user = random.choice(fake_names) + f"_{random.randint(10, 99)}"
    fake_user_id = random.randint(9000, 99999)
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"INSERT INTO giveaway_participants (giveaway_id, user_id, username, joined_at) VALUES ({p}, {p}, {p}, {p})",
                   (giveaway_id, fake_user_id, random_user, now))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"🎲 '{random_user}' kullanıcısı çekilişe başarıyla eklendi!", "success")
    return redirect(url_for("admin_panel"))

# --- ADMIN: ÇEKİLİŞTEN KATILIMCI SİLME ---
@app.route("/admin/giveaway/remove-participant/<int:participant_id>", methods=["POST"])
@admin_required
def admin_remove_participant(participant_id):
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"DELETE FROM giveaway_participants WHERE id = {p}", (participant_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Katılımcı çekilişten başarıyla çıkarıldı.", "info")
    return redirect(url_for("admin_panel"))

# --- ADMIN: ÇEKİLİŞİ ÇEK / KAZANANI BELİRLE ---
@app.route("/admin/giveaway/draw/<int:giveaway_id>", methods=["POST"])
@admin_required
def admin_draw_giveaway(giveaway_id):
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"

    cursor.execute(f"SELECT * FROM giveaways WHERE id = {p}", (giveaway_id,))
    gw = cursor.fetchone()

    if not gw or gw["status"] != "Aktif":
        cursor.close()
        conn.close()
        flash("Bu çekiliş zaten tamamlanmış veya geçersiz!", "warning")
        return redirect(url_for("admin_panel"))

    cursor.execute(f"SELECT username, user_id FROM giveaway_participants WHERE giveaway_id = {p}", (giveaway_id,))
    participants = cursor.fetchall()

    if not participants:
        cursor.close()
        conn.close()
        flash("Bu çekilişe henüz hiç kimse katılmadı!", "danger")
        return redirect(url_for("admin_panel"))

    winner = random.choice(participants)
    winner_name = winner["username"] if isinstance(winner, dict) else winner[0]
    winner_id = winner["user_id"] if isinstance(winner, dict) else winner[1]

    reward_code = generate_game_code(gw["reward"])

    cursor.execute(f"UPDATE giveaways SET status = 'Tamamlandı', winner_username = {p}, delivered_code = {p} WHERE id = {p}",
                   (winner_name, reward_code, giveaway_id))
    
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    cursor.execute(f"INSERT INTO orders (user_id, product_title, price, delivered_code, created_at) VALUES ({p}, {p}, 0.0, {p}, {p})",
                   (winner_id, f"🎁 Çekiliş Ödülü: {gw['reward']}", reward_code, now))
    conn.commit()
    cursor.close()
    conn.close()

    send_discord_log(
        title="🏆 Çekiliş Sonuçlandı!",
        description=(
            f"**Çekiliş:** `{gw['title']}`\n"
            f"**Ödül:** `{gw['reward']}`\n"
            f"**Kazanan:** 👑 `{winner_name}`\n"
            f"**Teslim Edilen Kod:** `{reward_code}`"
        ),
        color=15844367
    )

    flash(f"🎉 Çekiliş çekildi! Kazanan: '{winner_name}' | Ödül Kodu: '{reward_code}'", "success")
    return redirect(url_for("admin_panel"))

# --- ADMIN: ÇEKİLİŞ SİLME ---
@app.route("/admin/giveaway/delete/<int:giveaway_id>", methods=["POST"])
@admin_required
def admin_delete_giveaway(giveaway_id):
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"DELETE FROM giveaway_participants WHERE giveaway_id = {p}", (giveaway_id,))
    cursor.execute(f"DELETE FROM giveaways WHERE id = {p}", (giveaway_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Çekiliş silindi.", "info")
    return redirect(url_for("admin_panel"))

# --- RASTGELE HESAP OLUŞTURMA ---
@app.route("/admin/user/generate-random", methods=["POST"])
@admin_required
def admin_generate_random_user():
    random_id = random.randint(1000, 9999)
    random_username = f"user_{random_id}"
    random_raw_password = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    hashed_pw = generate_password_hash(random_raw_password)
    test_balance = 500.0

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    
    try:
        cursor.execute(f"INSERT INTO users (username, password, balance, is_admin) VALUES ({p}, {p}, {p}, 0)",
                       (random_username, hashed_pw, test_balance))
        conn.commit()
        flash(f"🎲 Rastgele Hesap Oluşturuldu! Kullanıcı: '{random_username}' | Şifre: '{random_raw_password}' | Bakiye: 500 TL", "success")
    except Exception as e:
        flash(f"Hesap oluşturulurken hata: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin_panel"))

# --- RASTGELE İLAN OLUŞTURMA ---
@app.route("/admin/product/generate-random", methods=["POST"])
@admin_required
def admin_generate_random_product():
    random_templates = [
        {"title": f"Valorant {random.choice([1200, 2480, 5350, 11000])} VP", "price": random.choice([150, 290, 580, 1150]), "image": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400", "main_cat": "oyun", "sub_cat": "valorant"},
        {"title": f"PUBG Mobile {random.choice([325, 660, 1800, 3850])} UC", "price": random.choice([110, 210, 550, 1100]), "image": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=400", "main_cat": "oyun", "sub_cat": "pubg"},
        {"title": f"Steam {random.choice([10, 20, 50, 100])} USD Cüzdan Kodu", "price": random.choice([340, 680, 1700, 3400]), "image": "https://images.unsplash.com/photo-1612287232231-30c14dbbb227?w=400", "main_cat": "oyun", "sub_cat": "steam"},
        {"title": f"Instagram {random.choice(['2.500', '5.000', '10.000'])} Organik Takipçi", "price": random.choice([55, 95, 175]), "image": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", "main_cat": "sosyal", "sub_cat": "instagram"},
        {"title": f"Instagram {random.choice(['5.000', '10.000', '25.000'])} Keşfet Etkili Beğeni", "price": random.choice([30, 60, 120]), "image": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=400", "main_cat": "sosyal", "sub_cat": "instagram"},
        {"title": f"TikTok {random.choice(['10.000', '50.000', '100.000'])} İzlenme & Paylaşım", "price": random.choice([40, 110, 190]), "image": "https://images.unsplash.com/photo-1596558450255-7c0b7be9d56a?w=400", "main_cat": "sosyal", "sub_cat": "tiktok"},
        {"title": f"YouTube {random.choice(['1.000', '4.000'])} İzlenme & Abone Paketi", "price": random.choice([130, 320]), "image": "https://images.unsplash.com/photo-1543269865-cbf427effbad?w=400", "main_cat": "sosyal", "sub_cat": "youtube"}
    ]
    
    item = random.choice(random_templates)
    stock = random.randint(150, 999)

    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    cursor.execute(f"INSERT INTO products (title, price, image, stock, main_category, sub_category) VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
                   (item["title"], float(item["price"]), item["image"], stock, item["main_cat"], item["sub_cat"]))
    conn.commit()
    cursor.close()
    conn.close()

    flash(f"🎲 Rastgele İlan Oluşturuldu: '{item['title']}'", "success")
    return redirect(url_for("admin_panel"))

# --- KULLANICI SİLME ---
@app.route("/admin/user/delete/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
    
    cursor.execute(f"SELECT username FROM users WHERE id = {p}", (user_id,))
    target = cursor.fetchone()
    
    if target:
        if target["username"] == SUPER_ADMIN_USERNAME:
            flash("⛔ Ana Süper Yönetici hesabı silinemez!", "danger")
        else:
            cursor.execute(f"DELETE FROM orders WHERE user_id = {p}", (user_id,))
            cursor.execute(f"DELETE FROM users WHERE id = {p}", (user_id,))
            conn.commit()
            flash(f"'{target['username']}' kullanıcısı silindi.", "info")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_panel"))

# --- ŞİFRE SIFIRLAMA ---
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

    flash(f"'{target_username}' şifresi güncellendi!", "success")
    return redirect(url_for("admin_panel"))

# --- ADMIN YETKİ ---
@app.route("/admin/user/toggle-admin/<int:user_id>", methods=["POST"])
@admin_required
def admin_toggle_role(user_id):
    current = get_current_user()
    if current["username"] != SUPER_ADMIN_USERNAME:
        flash("⛔ Yalnızca Süper Admin yetki verebilir!", "danger")
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
            flash(f"'{target['username']}' yetkisi güncellendi.", "success")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_panel"))

# --- MANUEL ÜRÜN EKLEME ---
@app.route("/admin/product/add", methods=["POST"])
@admin_required
def admin_add_product():
    title = request.form.get("title", "").strip()
    price = float(request.form.get("price", 0.0))
    image = request.form.get("image", "").strip()
    stock = int(request.form.get("stock", 100))
    main_cat = request.form.get("main_category", "oyun")
    sub_cat = request.form.get("sub_category", "genel")

    if title and price > 0:
        conn = get_db()
        cursor = conn.cursor()
        p = "%s" if (HAS_POSTGRES and DATABASE_URL) else "?"
        cursor.execute(f"INSERT INTO products (title, price, image, stock, main_category, sub_category) VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
                       (title, price, image, stock, main_cat, sub_cat))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Ürün eklendi.", "success")
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

    flash("Ürün güncellendi.", "success")
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
    flash("Ürün silindi.", "info")
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

    flash("Bakiye güncellendi.", "success")
    return redirect(url_for("admin_panel"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
