from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3, secrets, string, os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'gizli-anahtar-degistir'

DATABASE = 'platform.db'
YEMEKSEPETI_BASE = 'https://www.yemeksepeti.com'
ADMIN_PASSWORD = 'admin123'  # Gerçek kullanımda değiştir

# ── Veritabanı ──────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS developers (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            game_name TEXT NOT NULL,
            email     TEXT NOT NULL UNIQUE,
            ref_code  TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clicks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            developer_id INTEGER NOT NULL,
            clicked_at   TEXT NOT NULL,
            ip           TEXT,
            FOREIGN KEY (developer_id) REFERENCES developers(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            developer_id INTEGER NOT NULL,
            order_ref    TEXT NOT NULL,
            amount       REAL NOT NULL DEFAULT 0,
            commission   REAL NOT NULL DEFAULT 0,
            created_at   TEXT NOT NULL,
            FOREIGN KEY (developer_id) REFERENCES developers(id)
        );
    ''')
    db.commit()
    db.close()

def unique_ref_code(db):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(chars) for _ in range(8))
        row = db.execute('SELECT id FROM developers WHERE ref_code = ?', (code,)).fetchone()
        if not row:
            return code

# ── Auth yardımcıları ────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'developer_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ── Geliştirici Sayfaları ────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('register'))

@app.route('/kayit', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        name      = request.form['name'].strip()
        game_name = request.form['game_name'].strip()
        email     = request.form['email'].strip().lower()

        if not name or not game_name or not email:
            error = 'Tüm alanlar zorunludur.'
        else:
            db = get_db()
            exists = db.execute('SELECT id FROM developers WHERE email = ?', (email,)).fetchone()
            if exists:
                error = 'Bu e-posta adresi zaten kayıtlı.'
            else:
                ref_code = unique_ref_code(db)
                db.execute(
                    'INSERT INTO developers (name, game_name, email, ref_code, created_at) VALUES (?,?,?,?,?)',
                    (name, game_name, email, ref_code, datetime.utcnow().isoformat())
                )
                db.commit()
                dev = db.execute('SELECT * FROM developers WHERE email = ?', (email,)).fetchone()
                session['developer_id'] = dev['id']
                return redirect(url_for('dashboard'))
    return render_template('register.html', error=error)

@app.route('/giris', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        db = get_db()
        dev = db.execute('SELECT * FROM developers WHERE email = ?', (email,)).fetchone()
        if dev:
            session['developer_id'] = dev['id']
            return redirect(url_for('dashboard'))
        else:
            error = 'Bu e-posta ile kayıtlı geliştirici bulunamadı.'
    return render_template('login.html', error=error)

@app.route('/cikis')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    dev = db.execute('SELECT * FROM developers WHERE id = ?', (session['developer_id'],)).fetchone()
    clicks = db.execute(
        'SELECT COUNT(*) as cnt FROM clicks WHERE developer_id = ?', (dev['id'],)
    ).fetchone()['cnt']
    orders = db.execute(
        'SELECT COUNT(*) as cnt, COALESCE(SUM(commission),0) as total FROM orders WHERE developer_id = ?',
        (dev['id'],)
    ).fetchone()

    affiliate_link = url_for('redirect_affiliate', code=dev['ref_code'], _external=True)
    return render_template('dashboard.html',
        dev=dev,
        clicks=clicks,
        order_count=orders['cnt'],
        earnings=orders['total'],
        affiliate_link=affiliate_link
    )

# ── Affiliate yönlendirme ─────────────────────────────────────────────────────

@app.route('/git/<code>')
def redirect_affiliate(code):
    db = get_db()
    dev = db.execute('SELECT * FROM developers WHERE ref_code = ?', (code,)).fetchone()
    if not dev:
        return 'Geçersiz link.', 404
    db.execute(
        'INSERT INTO clicks (developer_id, clicked_at, ip) VALUES (?,?,?)',
        (dev['id'], datetime.utcnow().isoformat(), request.remote_addr)
    )
    db.commit()
    target = f"{YEMEKSEPETI_BASE}?ref={code}"
    return redirect(target)

# ── Admin ────────────────────────────────────────────────────────────────────

@app.route('/admin/giris', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        error = 'Hatalı şifre.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/cikis')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_required
def admin_panel():
    db = get_db()
    rows = db.execute('''
        SELECT d.*,
               COUNT(DISTINCT c.id)  AS clicks,
               COUNT(DISTINCT o.id)  AS orders,
               COALESCE(SUM(o.commission), 0) AS earnings
        FROM developers d
        LEFT JOIN clicks c ON c.developer_id = d.id
        LEFT JOIN orders o ON o.developer_id = d.id
        GROUP BY d.id
        ORDER BY d.created_at DESC
    ''').fetchall()
    return render_template('admin.html', developers=rows)

# ── Sipariş webhook (Yemeksepeti entegrasyonu buraya eklenecek) ──────────────

@app.route('/webhook/siparis', methods=['POST'])
def order_webhook():
    """
    Yemeksepeti gerçek entegrasyon kurulunca bu endpoint'e
    sipariş bildirimi gelecek. Şimdilik manuel test için açık.
    """
    data = request.get_json(silent=True) or {}
    ref_code  = data.get('ref')
    order_ref = data.get('order_id', secrets.token_hex(6))
    amount    = float(data.get('amount', 0))
    commission = round(amount * 0.05, 2)  # %5 komisyon

    if not ref_code:
        return {'ok': False, 'error': 'ref eksik'}, 400

    db = get_db()
    dev = db.execute('SELECT * FROM developers WHERE ref_code = ?', (ref_code,)).fetchone()
    if not dev:
        return {'ok': False, 'error': 'geliştirici bulunamadı'}, 404

    db.execute(
        'INSERT INTO orders (developer_id, order_ref, amount, commission, created_at) VALUES (?,?,?,?,?)',
        (dev['id'], order_ref, amount, commission, datetime.utcnow().isoformat())
    )
    db.commit()
    return {'ok': True}

# ── Başlat ───────────────────────────────────────────────────────────────────

# Uygulama ilk yüklendiğinde (gunicorn dahil) veritabanını başlat
if not os.path.exists(DATABASE):
    init_db()

port = int(os.environ.get('PORT', 8080))
app.run(host='0.0.0.0', port=port)
