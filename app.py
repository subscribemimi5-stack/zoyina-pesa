from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from models import db, User, Transaction, Advertisement, AdGroup, AdView, UserGroupProgress, SiteSettings, Message, Announcement, Article, RateLimit, PLATFORM_CONFIG
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import uuid, os, hashlib, time, hmac, secrets

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zoyina_pesa.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "zoyina_secret_2024")
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

ALLOWED_EXTENSIONS = {"mp4", "webm", "mov", "avi"}
REFERRAL_BONUS = 500.0
MIN_WITHDRAWAL = 2000.0
VIP_REFERRAL_THRESHOLD = 20
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

for d in ["static/uploads", "static/uploads/banners", "static/uploads/logos", "static/uploads/pictures"]:
    os.makedirs(d, exist_ok=True)
db.init_app(app)


# ══════════════════════════════════════════════
# ULINZI WA BOT — Security helpers
# ══════════════════════════════════════════════

# Muda wa kusubiri (seconds) kati ya maombi ya usajili kwa IP moja
REGISTER_RATE_LIMIT  = 5    # maombi 5 kwa dakika 15
REGISTER_WINDOW_MIN  = 15
REGISTER_BLOCK_MIN   = 60   # funga kwa saa 1

LOGIN_RATE_LIMIT     = 10   # maombi 10 kwa dakika 5
LOGIN_WINDOW_MIN     = 5
LOGIN_BLOCK_MIN      = 30   # funga kwa dakika 30

MAX_LOGIN_ATTEMPTS   = 5    # Majaribio ya nywila kabla ya kufunga akaunti
ACCOUNT_LOCK_MIN     = 30   # Dakika 30 za kufunga baada ya majaribio mengi

def _sign_token(payload: str) -> str:
    """Tengeneza saini ya HMAC-SHA256 kwa token ya honeypot."""
    key = app.config["SECRET_KEY"].encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()

def generate_form_token() -> str:
    """
    Tengeneza token ya wakati wa kutuma fomu.
    Format: <timestamp>.<nonce>.<signature>
    - Timestamp: wakati wa kutengeneza (epoch seconds)
    - Nonce: nasibu ya hexadecimal
    - Signature: HMAC — hakuna mtu anayeweza kuiunda bila SECRET_KEY
    """
    ts    = str(int(time.time()))
    nonce = secrets.token_hex(16)
    sig   = _sign_token(f"{ts}.{nonce}")
    return f"{ts}.{nonce}.{sig}"

def verify_form_token(token: str, min_seconds: int = 3, max_seconds: int = 3600) -> tuple:
    """
    Angalia token ya fomu. Rudisha (valid: bool, reason: str).
    - min_seconds: fomu lazima iwe imefunguliwa kwa sekunde hizi kabla ya kutuma
      (bot haraka mno → zinakataliwa)
    - max_seconds: fomu haikubaliki zaidi ya saa 1
    """
    if not token or token.count('.') != 2:
        return False, "token_missing"
    try:
        ts_str, nonce, sig = token.split('.')
        ts = int(ts_str)
    except (ValueError, AttributeError):
        return False, "token_invalid"

    # Thibitisha saini
    expected = _sign_token(f"{ts_str}.{nonce}")
    if not hmac.compare_digest(expected, sig):
        return False, "token_tampered"

    # Angalia muda
    age = int(time.time()) - ts
    if age < min_seconds:
        return False, "too_fast"      # Bot iliyojaza fomu haraka mno
    if age > max_seconds:
        return False, "token_expired"

    return True, "ok"

def get_real_ip() -> str:
    """Pata IP ya kweli hata nyuma ya proxy."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'

def ua_looks_like_bot() -> bool:
    """Angalia User-Agent kwa dalili za bot."""
    ua = (request.headers.get('User-Agent') or '').lower()
    if not ua or len(ua) < 10:
        return True
    BOT_KEYWORDS = [
        'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget', 'python-requests',
        'httpx', 'go-http-client', 'java/', 'libwww', 'okhttp', 'axios',
        'headless', 'phantom', 'selenium', 'puppeteer', 'playwright'
    ]
    return any(k in ua for k in BOT_KEYWORDS)

def allowed_file(f):
    return "." in f and f.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login_page"))
        return f(*a, **kw)
    return dec

def login_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*a, **kw)
    return dec

@app.context_processor
def inject_globals():
    try:
        outside = Announcement.query.filter(Announcement.is_active==True, Announcement.position.in_(['outside','both'])).order_by(Announcement.created_at.desc()).all()
        inside  = Announcement.query.filter(Announcement.is_active==True, Announcement.position.in_(['inside','both'])).order_by(Announcement.created_at.desc()).all()
        return {
            'site_name': SiteSettings.get('site_name','Zoyina Pesa'),
            'site_tagline': SiteSettings.get('tagline','Pata Pesa Kwa Urahisi'),
            'primary_color': SiteSettings.get('primary_color','#00C853'),
            'logo_filename': SiteSettings.get('logo_filename',''),
            'outside_announcements': outside,
            'inside_announcements': inside,
            'PLATFORM_CONFIG': PLATFORM_CONFIG,
        }
    except:
        return {'site_name':'Zoyina Pesa','site_tagline':'','primary_color':'#00C853','logo_filename':'','outside_announcements':[],'inside_announcements':[],'PLATFORM_CONFIG':PLATFORM_CONFIG}

def check_level_upgrade(user):
    if user.level==1 and user.referral_count >= int(SiteSettings.get("vip_threshold", str(VIP_REFERRAL_THRESHOLD))):
        user.level = 2
        user.can_view_ads = True
        return True
    if user.level==2 and not user.can_view_ads:
        user.can_view_ads = True
    return False

def today_str():
    return date.today().isoformat()

# ===================== PAGES =====================

@app.route("/")
def index():
    if "user_id" in session: return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/register_page")
def register_page():
    return render_template("register.html", ref_code=request.args.get("ref",""))

@app.route("/dashboard")
@login_required
def dashboard():
    user = User.query.get(session["user_id"])
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login_page"))
    if check_level_upgrade(user):
        db.session.commit()
    txs = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(10).all()
    # Vikundi vya leo vilivyokamilika
    done_groups = {p.group_id for p in UserGroupProgress.query.filter_by(user_id=user.id, date_key=today_str()).all()}
    groups = AdGroup.query.filter_by(is_active=True).order_by(AdGroup.platform, AdGroup.created_at.desc()).all() if user.can_view_ads else []
    # UI ya kibinafsi ya mtumiaji huyu
    raw_ui = {s.key: s.value for s in SiteSettings.query.filter(
        SiteSettings.key.like(f'ui_{user.id}_%')).all()}
    user_ui = type('UI', (), {k.replace(f'ui_{user.id}_', ''): v for k, v in raw_ui.items()})() if raw_ui else None
    return render_template("dashboard.html", user=user, transactions=txs,
        groups=groups, done_groups=done_groups,
        min_withdrawal=float(SiteSettings.get("min_withdrawal", str(MIN_WITHDRAWAL))),
        referral_bonus=float(SiteSettings.get("referral_bonus", str(REFERRAL_BONUS))),
        vip_threshold=int(SiteSettings.get("vip_threshold", str(VIP_REFERRAL_THRESHOLD))),
        PLATFORM_CONFIG=PLATFORM_CONFIG, user_ui=user_ui)

@app.route("/subscribe")
@login_required
def subscribe_page():
    user = User.query.get(session["user_id"])
    if user.is_subscribed: return redirect(url_for("dashboard"))
    return render_template("subscribe.html", youtube_url=SiteSettings.get("youtube_url",""))

@app.route("/confirm_subscribe", methods=["POST"])
@login_required
def confirm_subscribe():
    user = User.query.get(session["user_id"])
    user.is_subscribed = True
    db.session.commit()
    return jsonify({"status":"success","redirect":url_for("dashboard")})

# ===================== AUTH =====================

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    user_ip = request.remote_addr
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    phone = (data.get("phone") or "").strip()
    referred_by = (data.get("referred_by") or "").strip().upper()
    if not username or not password:
        return jsonify({"status":"error","message":"Jaza taarifa zote!"}), 400
    if len(username) < 3:
        return jsonify({"status":"error","message":"Username lazima iwe na herufi 3+!"}), 400
    if len(password) < 6:
        return jsonify({"status":"error","message":"Nywila lazima iwe na herufi 6+!"}), 400
    if User.query.filter_by(ip_address=user_ip).first():
        return jsonify({"status":"error","message":"Kifaa hiki kimeshasajiliwa!"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"status":"error","message":"Username imeshachukuliwa!"}), 400
    referrer = None
    if referred_by:
        referrer = User.query.filter_by(referral_code=referred_by).first()
        if not referrer:
            return jsonify({"status":"error","message":"Nambari ya rufaa si sahihi!"}), 400
    bonus = float(SiteSettings.get("referral_bonus","500"))
    new_user = User(username=username, password=generate_password_hash(password),
        password_plain=password, phone=phone, ip_address=user_ip,
        referral_code=uuid.uuid4().hex[:8].upper(),
        referred_by=referred_by if referred_by else None, balance=0.0, total_earned=0.0, level=1)
    try:
        db.session.add(new_user)
        db.session.flush()
        if referrer:
            referrer.balance += bonus; referrer.total_earned += bonus
            check_level_upgrade(referrer)
            db.session.add(Transaction(user_id=referrer.id, amount=bonus, transaction_type="Earning",
                description=f"Bonus ya rufaa kutoka kwa {username}", status="Completed"))
        db.session.commit()
        return jsonify({"status":"success","message":"Usajili umekamilika! Ingia sasa."}), 201
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"status":"error","message":"Username au Nywila si sahihi!"}), 401
    if not user.is_active: return jsonify({"status":"error","message":"Akaunti yako imefungwa!"}), 403
    if check_password_hash(user.password, password):
        session.clear(); session["user_id"] = user.id
        return jsonify({"status":"success","redirect":"/subscribe" if not user.is_subscribed else "/dashboard"})
    return jsonify({"status":"error","message":"Username au Nywila si sahihi!"}), 401

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login_page"))

@app.route("/withdraw", methods=["POST"])
@login_required
def withdraw():
    data = request.get_json()
    user = User.query.get(session["user_id"])
    amount = float(data.get("amount", 0))
    phone = (data.get("phone") or "").strip()
    min_w = float(SiteSettings.get("min_withdrawal","2000"))
    if amount < min_w: return jsonify({"status":"error","message":f"Kiwango cha chini ni Tsh {min_w:,.0f}!"}), 400
    if user.balance < amount: return jsonify({"status":"error","message":"Salio halitosha!"}), 400
    if not phone: return jsonify({"status":"error","message":"Weka nambari ya simu!"}), 400
    try:
        user.balance -= amount
        db.session.add(Transaction(user_id=user.id, amount=amount, transaction_type="Withdrawal",
            description=f"Ombi la kutoa - {phone}", status="Pending"))
        db.session.commit()
        return jsonify({"status":"success","message":f"Ombi la Tsh {amount:,.0f} limepokelewa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

# ===================== ADMIN AUTH =====================

@app.route("/admin")
def admin_login_page():
    if session.get("is_admin"): return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")

@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if data.get("username")==ADMIN_USERNAME and data.get("password")==ADMIN_PASSWORD:
        session["is_admin"] = True
        return jsonify({"status":"success","redirect":url_for("admin_dashboard")})
    return jsonify({"status":"error","message":"Taarifa si sahihi!"}), 401

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login_page"))

# ===================== ADMIN DASHBOARD =====================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    users = User.query.filter(~User.username.like('ref_%')).order_by(User.created_at.desc()).all()
    pending_withdrawals = Transaction.query.filter_by(transaction_type="Withdrawal", status="Pending").order_by(Transaction.created_at.desc()).all()
    groups = AdGroup.query.order_by(AdGroup.platform, AdGroup.created_at.desc()).all()
    ads = Advertisement.query.order_by(Advertisement.created_at.desc()).all()
    settings = {s.key: s.value for s in SiteSettings.query.all()}
    stats = {
        "total_users": User.query.filter(~User.username.like('ref_%')).count(),
        "vip_users": User.query.filter_by(level=2).filter(~User.username.like('ref_%')).count(),
        "total_balance": db.session.query(db.func.sum(User.balance)).scalar() or 0,
        "total_paid": db.session.query(db.func.sum(Transaction.amount)).filter_by(transaction_type="Withdrawal", status="Completed").scalar() or 0,
        "pending_count": Transaction.query.filter_by(transaction_type="Withdrawal", status="Pending").count(),
        "total_ads": Advertisement.query.filter_by(is_active=True).count(),
        "total_groups": AdGroup.query.filter_by(is_active=True).count(),
    }
    return render_template("admin_dashboard.html", users=users, pending_withdrawals=pending_withdrawals,
        groups=groups, ads=ads, settings=settings, stats=stats, PLATFORM_CONFIG=PLATFORM_CONFIG)

@app.route("/admin/settings", methods=["POST"])
@admin_required
def admin_settings():
    data = request.get_json()
    for key in ["referral_bonus","min_withdrawal","vip_threshold","youtube_url"]:
        val = (data.get(key) or "").strip()
        if val: SiteSettings.set(key, val)
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"Mipangilio imesasishwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

# ===================== ADMIN AD GROUPS =====================

@app.route("/admin/groups/add", methods=["POST"])
@admin_required
def add_group():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    platform = data.get("platform", "other")
    description = (data.get("description") or "").strip()
    reward_per_ad = float(data.get("reward_per_ad", 500))
    min_level = int(data.get("min_level", 1))
    # Muda wa kutazama kutoka config ya platform au custom
    cfg = PLATFORM_CONFIG.get(platform, PLATFORM_CONFIG['other'])
    watch_seconds = int(data.get("watch_seconds", cfg['min_seconds']))
    if not name:
        return jsonify({"status":"error","message":"Weka jina la kikundi!"}), 400
    g = AdGroup(name=name, platform=platform, description=description,
        watch_seconds=watch_seconds, reward_per_ad=reward_per_ad, min_level=min_level)
    try:
        db.session.add(g)
        db.session.commit()
        return jsonify({"status":"success","message":f"Kikundi '{name}' kimeongezwa!","id":g.id})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route("/admin/groups/<int:gid>/edit", methods=["POST"])
@admin_required
def edit_group(gid):
    g = AdGroup.query.get_or_404(gid)
    data = request.get_json()
    if data.get("name"): g.name = data["name"].strip()
    if data.get("platform"): g.platform = data["platform"]
    if data.get("description") is not None: g.description = data["description"].strip()
    if data.get("reward_per_ad"): g.reward_per_ad = float(data["reward_per_ad"])
    if data.get("watch_seconds"): g.watch_seconds = int(data["watch_seconds"])
    if data.get("min_level"): g.min_level = int(data["min_level"])
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"Kikundi kimesasishwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route("/admin/groups/<int:gid>/toggle", methods=["POST"])
@admin_required
def toggle_group(gid):
    g = AdGroup.query.get_or_404(gid)
    g.is_active = not g.is_active
    db.session.commit()
    return jsonify({"status":"success","is_active":g.is_active,"message":f"Kikundi {'kimewashwa' if g.is_active else 'kimezimwa'}!"})

@app.route("/admin/groups/<int:gid>/delete", methods=["POST"])
@admin_required
def delete_group(gid):
    g = AdGroup.query.get_or_404(gid)
    # Futa faili za video za matangazo yote
    for ad in g.ads:
        if ad.video_filename:
            path = os.path.join(app.config["UPLOAD_FOLDER"], ad.video_filename)
            if os.path.exists(path): os.remove(path)
    try:
        db.session.delete(g)
        db.session.commit()
        return jsonify({"status":"success","message":"Kikundi na matangazo yake yamefutwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

# ===================== ADMIN ADS =====================

@app.route("/admin/ads/add", methods=["POST"])
@admin_required
def add_ad():
    title = request.form.get("title","").strip()
    group_id = request.form.get("group_id","")
    video_type = request.form.get("video_type","url")
    reward = float(request.form.get("reward", 0))
    min_level = int(request.form.get("min_level", 1))

    if not title:
        return jsonify({"status":"error","message":"Weka kichwa cha tangazo!"}), 400

    # Pata kikundi na inherit platform/watch_seconds
    group = None
    platform = request.form.get("platform","other")
    watch_seconds = int(request.form.get("watch_seconds", 60))

    if group_id:
        group = AdGroup.query.get(int(group_id))
        if group:
            platform = group.platform
            watch_seconds = group.watch_seconds
            if reward == 0: reward = group.reward_per_ad
            if min_level == 1: min_level = group.min_level

    ad = Advertisement(title=title, platform=platform, video_type=video_type,
        watch_seconds=watch_seconds, reward=reward, min_level=min_level,
        description=request.form.get("description","").strip(),
        group_id=group.id if group else None)

    if video_type == "url":
        video_url = request.form.get("video_url","").strip()
        if not video_url:
            return jsonify({"status":"error","message":"Weka URL ya video!"}), 400
        ad.video_url = video_url
    else:
        if "video_file" not in request.files:
            return jsonify({"status":"error","message":"Chagua faili ya video!"}), 400
        file = request.files["video_file"]
        if not file.filename or not allowed_file(file.filename):
            return jsonify({"status":"error","message":"Aina ya faili haikubaliki!"}), 400
        filename = uuid.uuid4().hex + "_" + secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        ad.video_filename = filename

    try:
        db.session.add(ad)
        db.session.commit()
        return jsonify({"status":"success","message":"Tangazo limeongezwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route("/admin/ads/<int:ad_id>/edit", methods=["POST"])
@admin_required
def edit_ad(ad_id):
    ad = Advertisement.query.get_or_404(ad_id)
    data = request.form
    if data.get("title"): ad.title = data["title"].strip()
    if data.get("description") is not None: ad.description = data["description"].strip()
    if data.get("reward"): ad.reward = float(data["reward"])
    if data.get("watch_seconds"): ad.watch_seconds = int(data["watch_seconds"])
    if data.get("video_url"): ad.video_url = data["video_url"].strip()
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"Tangazo limesasishwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route("/admin/ads/<int:ad_id>/toggle", methods=["POST"])
@admin_required
def toggle_ad(ad_id):
    ad = Advertisement.query.get_or_404(ad_id)
    ad.is_active = not ad.is_active
    db.session.commit()
    return jsonify({"status":"success","is_active":ad.is_active,"message":f"Tangazo {'limewashwa' if ad.is_active else 'limezimwa'}!"})

@app.route("/admin/ads/<int:ad_id>/delete", methods=["POST"])
@admin_required
def delete_ad(ad_id):
    ad = Advertisement.query.get_or_404(ad_id)
    if ad.video_filename:
        path = os.path.join(app.config["UPLOAD_FOLDER"], ad.video_filename)
        if os.path.exists(path): os.remove(path)
    try:
        db.session.delete(ad)
        db.session.commit()
        return jsonify({"status":"success","message":"Tangazo limefutwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

# ===================== ADMIN USERS =====================

@app.route("/admin/user/<int:uid>")
@admin_required
def admin_user(uid):
    user = User.query.get_or_404(uid)
    txs = Transaction.query.filter_by(user_id=uid).order_by(Transaction.created_at.desc()).all()
    return render_template("admin_user.html", user=user, transactions=txs)

@app.route("/admin/user/<int:uid>/delete", methods=["POST"])
@admin_required
def admin_delete_user(uid):
    user = User.query.get_or_404(uid)
    try:
        Transaction.query.filter_by(user_id=uid).delete()
        AdView.query.filter_by(user_id=uid).delete()
        UserGroupProgress.query.filter_by(user_id=uid).delete()
        Message.query.filter_by(recipient_id=uid).delete()
        db.session.delete(user)
        db.session.commit()
        return jsonify({"status":"success","message":f"Mtumiaji {user.username} amefutwa!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error","message":str(e)}), 500

@app.route("/admin/withdrawal/<int:tx_id>/<action>", methods=["POST"])
@admin_required
def handle_withdrawal(tx_id, action):
    tx = Transaction.query.get_or_404(tx_id)
    if action == "approve":
        tx.status = "Completed"
        msg = "Malipo yameidhinishwa!"
    elif action == "reject":
        user = User.query.get(tx.user_id)
        if user: user.balance += tx.amount
        tx.status = "Rejected"
        msg = "Malipo yamekataliwa!"
    else:
        return jsonify({"status":"error","message":"Kitendo kisicho sahihi!"}), 400
    db.session.commit()
    return jsonify({"status":"success","message":msg})

@app.route("/admin/user/<int:uid>/balance", methods=["POST"])
@admin_required
def admin_set_balance(uid):
    data = request.get_json()
    user = User.query.get_or_404(uid)
    action = data.get("action"); amount = float(data.get("amount",0))
    if amount <= 0: return jsonify({"status":"error","message":"Weka kiasi sahihi!"}), 400
    if action == "add": user.balance += amount; user.total_earned += amount; desc=f"Admin ameongeza Tsh {amount:,.0f}"
    elif action == "deduct":
        if user.balance < amount: return jsonify({"status":"error","message":"Salio halitosha!"}), 400
        user.balance -= amount; desc=f"Admin amepunguza Tsh {amount:,.0f}"
    elif action == "set": user.balance = amount; desc=f"Admin ameweka salio Tsh {amount:,.0f}"
    else: return jsonify({"status":"error","message":"Kitendo kisicho sahihi!"}), 400
    db.session.add(Transaction(user_id=user.id, amount=amount, transaction_type="Admin", description=desc, status="Completed"))
    db.session.commit()
    return jsonify({"status":"success","message":desc,"new_balance":user.balance})

@app.route("/admin/user/<int:uid>/toggle", methods=["POST"])
@admin_required
def admin_toggle_user(uid):
    user = User.query.get_or_404(uid)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({"status":"success","is_active":user.is_active,"message":f"Akaunti ya {user.username} {'imewashwa' if user.is_active else 'imefungwa'}!"})

@app.route("/admin/user/<int:uid>/toggle_subscribe", methods=["POST"])
@admin_required
def admin_toggle_subscribe(uid):
    user = User.query.get_or_404(uid)
    user.is_subscribed = not user.is_subscribed
    db.session.commit()
    return jsonify({"status":"success","is_subscribed":user.is_subscribed})

@app.route("/admin/user/<int:uid>/toggle_ads", methods=["POST"])
@admin_required
def admin_toggle_ads(uid):
    user = User.query.get_or_404(uid)
    user.can_view_ads = not user.can_view_ads
    db.session.commit()
    return jsonify({"status":"success","can_view_ads":user.can_view_ads,"message":f"Matangazo ya {user.username} {'zimewashwa' if user.can_view_ads else 'zimezimwa'}!"})

@app.route("/admin/user/<int:uid>/set_level", methods=["POST"])
@admin_required
def admin_set_level(uid):
    data = request.get_json()
    user = User.query.get_or_404(uid)
    level = int(data.get("level",1))
    if level not in [1,2]: return jsonify({"status":"error","message":"Level lazima iwe 1 au 2!"}), 400
    user.level = level
    if data.get("enable_ads",True): user.can_view_ads = True
    db.session.commit()
    return jsonify({"status":"success","message":f"Level ya {user.username} imewekwa {level}!","new_balance":user.balance,"can_view_ads":user.can_view_ads})

@app.route("/admin/user/<int:uid>/reset_password", methods=["POST"])
@admin_required
def admin_reset_password(uid):
    data = request.get_json()
    user = User.query.get_or_404(uid)
    new_pw = (data.get("new_password") or "").strip()
    if len(new_pw) < 6: return jsonify({"status":"error","message":"Nywila lazima iwe na herufi 6+!"}), 400
    user.password = generate_password_hash(new_pw); user.password_plain = new_pw
    db.session.commit()
    return jsonify({"status":"success","message":f"Nywila ya {user.username} imebadilishwa!"})

# ===================== ADMIN REFERRALS =====================

@app.route("/admin/referrals")
@admin_required
def admin_referrals():
    users = User.query.filter_by(is_active=True).filter(~User.username.like('ref_%')).order_by(User.created_at.desc()).all()
    return render_template("admin_referrals.html", users=users, referral_bonus=float(SiteSettings.get("referral_bonus","500")))

@app.route("/admin/user/<int:uid>/add_referral", methods=["POST"])
@admin_required
def admin_add_referral(uid):
    data = request.get_json()
    user = User.query.get_or_404(uid)
    count = int(data.get("count",1))
    give_bonus = data.get("give_bonus", True)
    if count < 1 or count > 100: return jsonify({"status":"error","message":"Idadi lazima iwe 1-100!"}), 400
    bonus_per = float(SiteSettings.get("referral_bonus","500"))
    total_bonus = 0.0
    for _ in range(count):
        ghost = User(username=f"ref_{user.referral_code}_{uuid.uuid4().hex[:6]}",
            password="ghost", ip_address=f"fake_{uuid.uuid4().hex[:12]}",
            referral_code=uuid.uuid4().hex[:8].upper(), referred_by=user.referral_code,
            balance=0.0, total_earned=0.0, is_active=False, level=1)
        db.session.add(ghost)
    if give_bonus:
        total_bonus = bonus_per * count
        user.balance += total_bonus; user.total_earned += total_bonus
        db.session.add(Transaction(user_id=user.id, amount=total_bonus, transaction_type="Earning",
            description=f"Admin ameongeza rufaa {count}", status="Completed"))
    check_level_upgrade(user)
    db.session.commit()
    msg = f"Rufaa {count} zimeongezwa!"
    if give_bonus: msg += f" Bonus Tsh {total_bonus:,.0f}."
    return jsonify({"status":"success","message":msg,"new_referral_count":user.referral_count,"new_balance":user.balance})

@app.route("/admin/user/<int:uid>/remove_referral", methods=["POST"])
@admin_required
def admin_remove_referral(uid):
    """Futa rufaa za ghost (zilizotengenezwa na admin) kwa mtumiaji"""
    data = request.get_json()
    user = User.query.get_or_404(uid)
    count = int(data.get("count", 1))
    deduct_bonus = data.get("deduct_bonus", False)

    # Pata ghost users wa mtumiaji huyu
    ghosts = User.query.filter(
        User.referred_by == user.referral_code,
        User.username.like('ref_%'),
        User.is_active == False
    ).order_by(User.created_at.desc()).limit(count).all()

    removed = len(ghosts)
    if removed == 0:
        return jsonify({"status":"error","message":"Hakuna rufaa za kufuta!"}), 400

    for ghost in ghosts:
        db.session.delete(ghost)

    if deduct_bonus:
        bonus_per = float(SiteSettings.get("referral_bonus","500"))
        deduct = bonus_per * removed
        user.balance = max(0, user.balance - deduct)
        db.session.add(Transaction(user_id=user.id, amount=deduct, transaction_type="Admin",
            description=f"Admin amefuta rufaa {removed} (punguzo Tsh {deduct:,.0f})", status="Completed"))

    db.session.commit()
    return jsonify({"status":"success","message":f"Rufaa {removed} zimefutwa kwa {user.username}!",
        "new_referral_count":user.referral_count,"new_balance":user.balance})

@app.route("/admin/user/<int:uid>/friends")
@admin_required
def admin_user_friends(uid):
    user = User.query.get_or_404(uid)
    friends = User.query.filter(User.referred_by==user.referral_code, ~User.username.like('ref_%')).order_by(User.created_at.desc()).all()
    ghost_referrals = User.query.filter(User.referred_by==user.referral_code, User.username.like('ref_%')).count()
    referral_txs = Transaction.query.filter(Transaction.user_id==user.id, Transaction.transaction_type=="Earning", Transaction.description.like('%rufaa%')).order_by(Transaction.created_at.desc()).all()
    return render_template("admin_user_friends.html", user=user, friends=friends, ghost_referrals=ghost_referrals,
        referral_txs=referral_txs, referral_bonus=float(SiteSettings.get("referral_bonus","500")))

# ===================== ADS (USER) =====================

@app.route('/ads')
@login_required
def ads_page():
    user = User.query.get(session['user_id'])
    if not user.can_view_ads: return redirect(url_for('dashboard'))
    groups = AdGroup.query.filter_by(is_active=True).order_by(AdGroup.platform, AdGroup.created_at.desc()).all()
    # Matangazo aliyokwisha yatazama leo
    today_ad_views = {v.ad_id for v in AdView.query.filter(AdView.user_id==user.id, db.func.date(AdView.watched_at)==date.today()).all()}
    # Vikundi vilivyokamilika leo
    done_groups = {p.group_id for p in UserGroupProgress.query.filter_by(user_id=user.id, date_key=today_str()).all()}
    total_earned_today = sum(v.reward for v in AdView.query.filter(AdView.user_id==user.id, db.func.date(AdView.watched_at)==date.today()).all())
    return render_template('ads.html', user=user, groups=groups,
        today_ad_views=today_ad_views, done_groups=done_groups,
        total_earned_today=total_earned_today, PLATFORM_CONFIG=PLATFORM_CONFIG)

@app.route('/ads/group/<int:gid>')
@login_required
def group_ads_page(gid):
    user = User.query.get(session['user_id'])
    if not user.can_view_ads: return redirect(url_for('dashboard'))
    group = AdGroup.query.get_or_404(gid)
    if not group.is_active: return redirect(url_for('ads_page'))
    # Angalia kama kikundi kimekamilika leo
    done = UserGroupProgress.query.filter_by(user_id=user.id, group_id=gid, date_key=today_str()).first()
    # Matangazo ya kikundi — yanayofanya kazi
    ads = Advertisement.query.filter_by(group_id=gid, is_active=True).order_by(Advertisement.order_num, Advertisement.created_at).all()
    # Ni yapi aliyokwisha yatazama leo
    today_ad_views = {v.ad_id for v in AdView.query.filter(AdView.user_id==user.id, db.func.date(AdView.watched_at)==date.today()).all()}
    # Tangazo la sasa (la kwanza ambalo bado hajakumaliza)
    next_ad = next((a for a in ads if a.id not in today_ad_views), None)
    cfg = PLATFORM_CONFIG.get(group.platform, PLATFORM_CONFIG['other'])
    return render_template('group_ads.html', user=user, group=group, ads=ads,
        today_ad_views=today_ad_views, done=done, next_ad=next_ad, cfg=cfg)

@app.route('/ads/<int:ad_id>/play')
@login_required
def play_ad(ad_id):
    user = User.query.get(session['user_id'])
    if not user.can_view_ads: return redirect(url_for('dashboard'))
    ad = Advertisement.query.get_or_404(ad_id)
    if not ad.is_active: return redirect(url_for('ads_page'))
    # Angalia kama ameshakitazama leo
    already = AdView.query.filter(AdView.user_id==user.id, AdView.ad_id==ad_id, db.func.date(AdView.watched_at)==date.today()).first()
    cfg = PLATFORM_CONFIG.get(ad.platform, PLATFORM_CONFIG['other'])
    group = AdGroup.query.get(ad.group_id) if ad.group_id else None
    return render_template('ad_player.html', user=user, ad=ad, already_watched=already is not None,
        watch_seconds=ad.watch_seconds, cfg=cfg, group=group)

@app.route('/ads/<int:ad_id>/complete', methods=['POST'])
@login_required
def complete_ad(ad_id):
    user = User.query.get(session['user_id'])
    if not user.can_view_ads: return jsonify({"status":"error","message":"Hauruhusiwi!"}), 403
    ad = Advertisement.query.get_or_404(ad_id)
    already = AdView.query.filter(AdView.user_id==user.id, AdView.ad_id==ad_id, db.func.date(AdView.watched_at)==date.today()).first()
    if already: return jsonify({"status":"error","message":"Umeshakitazama tangazo hili leo!"}), 400
    try:
        user.balance += ad.reward; user.total_earned += ad.reward
        db.session.add(AdView(user_id=user.id, ad_id=ad_id, reward=ad.reward))
        db.session.add(Transaction(user_id=user.id, amount=ad.reward, transaction_type="Earning",
            description=f"Malipo ya kutazama: {ad.title}", status="Completed"))

        # Angalia kama kikundi kimekamilika
        next_ad_in_group = None
        group_completed = False
        if ad.group_id:
            group = AdGroup.query.get(ad.group_id)
            group_ads = Advertisement.query.filter_by(group_id=ad.group_id, is_active=True).all()
            viewed_ids = {v.ad_id for v in AdView.query.filter(AdView.user_id==user.id, db.func.date(AdView.watched_at)==date.today()).all()}
            viewed_ids.add(ad_id)  # jumuisha hili tulilokamilisha sasa hivi
            remaining = [a for a in group_ads if a.id not in viewed_ids]
            if not remaining:
                # Kikundi kimekamilika!
                group_completed = True
                if not UserGroupProgress.query.filter_by(user_id=user.id, group_id=ad.group_id, date_key=today_str()).first():
                    db.session.add(UserGroupProgress(user_id=user.id, group_id=ad.group_id,
                        completed_at=datetime.utcnow(), date_key=today_str()))
            else:
                next_ad_in_group = remaining[0].id

        db.session.commit()
        return jsonify({
            "status": "success",
            "message": f"Hongera! Umepata Tsh {ad.reward:,.0f}",
            "reward": ad.reward,
            "new_balance": user.balance,
            "next_ad_id": next_ad_in_group,
            "group_completed": group_completed,
            "group_id": ad.group_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status":"error","message":str(e)}), 500

# ===================== INBOX =====================

@app.route('/inbox')
@login_required
def inbox():
    user = User.query.get(session['user_id'])
    msgs = Message.query.filter_by(recipient_id=user.id).order_by(Message.created_at.desc()).all()
    unread = sum(1 for m in msgs if not m.is_read)
    return render_template('inbox.html', user=user, messages=msgs, unread=unread)

@app.route('/inbox/<int:msg_id>')
@login_required
def read_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.recipient_id != session['user_id']: return redirect(url_for('inbox'))
    if not msg.is_read: msg.is_read = True; db.session.commit()
    user = User.query.get(session['user_id'])
    msgs = Message.query.filter_by(recipient_id=user.id).order_by(Message.created_at.desc()).all()
    unread = sum(1 for m in msgs if not m.is_read)
    return render_template('inbox.html', user=user, messages=msgs, unread=unread, active_msg=msg)

@app.route('/inbox/<int:msg_id>/delete', methods=['POST'])
@login_required
def delete_my_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.recipient_id != session['user_id']: return jsonify({"status":"error"}), 403
    db.session.delete(msg); db.session.commit()
    return jsonify({"status":"success","redirect":url_for('inbox')})

@app.route('/api/inbox/unread')
@login_required
def inbox_unread_count():
    return jsonify({"unread": Message.query.filter_by(recipient_id=session['user_id'], is_read=False).count()})

@app.route('/messages/read/<int:msg_id>', methods=['POST'])
@login_required
def mark_read(msg_id):
    msg = Message.query.get_or_404(msg_id)
    if msg.recipient_id == session['user_id']: msg.is_read = True; db.session.commit()
    return jsonify({"status":"success"})

# ===================== ADMIN MESSAGES =====================

@app.route('/admin/messages')
@admin_required
def admin_messages():
    users = User.query.filter(~User.username.like('ref_%')).order_by(User.username).all()
    messages = Message.query.order_by(Message.created_at.desc()).limit(50).all()
    return render_template('admin_messages.html', users=users, messages=messages)

@app.route('/admin/messages/send', methods=['POST'])
@admin_required
def send_message():
    data = request.get_json()
    body = (data.get('body') or '').strip()
    if not body: return jsonify({"status":"error","message":"Weka maudhui ya mseji!"}), 400
    subject = (data.get('subject') or '').strip()
    rid = data.get('recipient_id')
    if data.get('recipient_type') == 'all':
        users = User.query.filter(~User.username.like('ref_%')).all()
        for u in users: db.session.add(Message(recipient_id=u.id, recipient_type='all', subject=subject, body=body))
        db.session.commit()
        return jsonify({"status":"success","message":f"Mseji umetumwa kwa watumiaji {len(users)}!"})
    if not rid: return jsonify({"status":"error","message":"Chagua mtumiaji!"}), 400
    db.session.add(Message(recipient_id=int(rid), recipient_type='single', subject=subject, body=body))
    db.session.commit()
    u = User.query.get(int(rid))
    return jsonify({"status":"success","message":f"Mseji umetumwa kwa {u.username}!"})

@app.route('/admin/messages/<int:msg_id>/delete', methods=['POST'])
@admin_required
def delete_message(msg_id):
    msg = Message.query.get_or_404(msg_id)
    db.session.delete(msg); db.session.commit()
    return jsonify({"status":"success","message":"Mseji umefutwa!"})

# ===================== ADMIN USERS — ACTIVE/INACTIVE FILTER =====================

@app.route('/admin/users/active')
@admin_required
def admin_users_active():
    """Watumiaji wanaofanya kazi (is_active=True)"""
    users = User.query.filter(
        User.is_active == True,
        ~User.username.like('ref_%')
    ).order_by(User.created_at.desc()).all()
    return jsonify([_user_dict(u) for u in users])

@app.route('/admin/users/inactive')
@admin_required
def admin_users_inactive():
    """Watumiaji waliofungwa (is_active=False)"""
    users = User.query.filter(
        User.is_active == False,
        ~User.username.like('ref_%')
    ).order_by(User.created_at.desc()).all()
    return jsonify([_user_dict(u) for u in users])

@app.route('/admin/users/stats')
@admin_required
def admin_users_stats():
    """Takwimu za haraka kwa ajili ya filter bar"""
    total    = User.query.filter(~User.username.like('ref_%')).count()
    active   = User.query.filter(User.is_active==True,  ~User.username.like('ref_%')).count()
    inactive = User.query.filter(User.is_active==False, ~User.username.like('ref_%')).count()
    vip      = User.query.filter(User.level==2, ~User.username.like('ref_%')).count()
    can_ads  = User.query.filter(User.is_active==True, User.can_view_ads==True, ~User.username.like('ref_%')).count()
    return jsonify({
        'total': total, 'active': active,
        'inactive': inactive, 'vip': vip, 'can_ads': can_ads
    })

def _user_dict(u):
    return {
        'id': u.id, 'username': u.username, 'phone': u.phone or '',
        'balance': u.balance, 'total_earned': u.total_earned,
        'level': u.level, 'is_active': u.is_active,
        'is_subscribed': u.is_subscribed, 'can_view_ads': u.can_view_ads,
        'referral_count': u.referral_count,
        'referral_code': u.referral_code or '',
        'created_at': u.created_at.strftime('%d %b %Y') if u.created_at else '',
    }

# ===================== ADMIN MESSAGES — GROUP SEND =====================

@app.route('/admin/messages/send_group', methods=['POST'])
@admin_required
def send_message_group():
    """
    Tuma mseji kwa kikundi maalum:
      group = 'active'    — watumiaji wote wanaofanya kazi
      group = 'inactive'  — watumiaji wote waliofungwa
      group = 'vip'       — watumiaji wa ngazi ya 2
      group = 'can_ads'   — watumiaji wenye ruhusa ya matangazo
      group = 'no_ads'    — watumiaji bila ruhusa ya matangazo
      group = 'single'    — mtumiaji mmoja (inahitaji recipient_id)
      group = 'all'       — wote
    """
    data    = request.get_json(silent=True) or {}
    group   = (data.get('group') or '').strip()
    subject = (data.get('subject') or '').strip()
    body    = (data.get('body') or '').strip()

    if not body:
        return jsonify({"status":"error","message":"Weka maudhui ya mseji!"}), 400
    if not group:
        return jsonify({"status":"error","message":"Chagua kikundi!"}), 400

    base_q = User.query.filter(~User.username.like('ref_%'))

    if group == 'active':
        users = base_q.filter(User.is_active==True).all()
        label = "watumiaji wanaofanya kazi"
    elif group == 'inactive':
        users = base_q.filter(User.is_active==False).all()
        label = "watumiaji waliofungwa"
    elif group == 'vip':
        users = base_q.filter(User.level==2).all()
        label = "watumiaji VIP (ngazi 2)"
    elif group == 'can_ads':
        users = base_q.filter(User.is_active==True, User.can_view_ads==True).all()
        label = "watumiaji wenye matangazo"
    elif group == 'no_ads':
        users = base_q.filter(User.is_active==True, User.can_view_ads==False).all()
        label = "watumiaji bila matangazo"
    elif group == 'all':
        users = base_q.all()
        label = "watumiaji wote"
    elif group == 'single':
        rid = data.get('recipient_id')
        if not rid:
            return jsonify({"status":"error","message":"Taja recipient_id!"}), 400
        u = User.query.get(int(rid))
        if not u:
            return jsonify({"status":"error","message":"Mtumiaji hapatikani!"}), 404
        db.session.add(Message(
            recipient_id=u.id, recipient_type='single',
            subject=subject, body=body
        ))
        db.session.commit()
        return jsonify({"status":"success","message":f"Mseji umetumwa kwa {u.username}!"})
    else:
        return jsonify({"status":"error","message":f"Kikundi '{group}' hakijulikani!"}), 400

    if not users:
        return jsonify({"status":"error","message":f"Hakuna watumiaji katika {label}!"}), 400

    for u in users:
        db.session.add(Message(
            recipient_id=u.id,
            recipient_type='group',
            subject=subject,
            body=body
        ))
    db.session.commit()
    return jsonify({
        "status": "success",
        "message": f"Mseji umetumwa kwa {len(users)} {label}!",
        "count": len(users)
    })

@app.route('/admin/users_panel')
@admin_required
def admin_users_panel():
    """Ukurasa mpya wa usimamizi wa watumiaji na filtering"""
    all_users = User.query.filter(~User.username.like('ref_%')).order_by(User.created_at.desc()).all()
    stats = {
        'total':    len(all_users),
        'active':   sum(1 for u in all_users if u.is_active),
        'inactive': sum(1 for u in all_users if not u.is_active),
        'vip':      sum(1 for u in all_users if u.level == 2),
        'can_ads':  sum(1 for u in all_users if u.can_view_ads and u.is_active),
    }
    return render_template('admin_users_panel.html', users=all_users, stats=stats)

# ===================== ANNOUNCEMENTS =====================

@app.route('/admin/announcements')
@admin_required
def admin_announcements():
    return render_template('admin_announcements.html', announcements=Announcement.query.order_by(Announcement.created_at.desc()).all())

@app.route('/admin/announcements/add', methods=['POST'])
@admin_required
def add_announcement():
    body = request.form.get('body','').strip()
    if not body: return jsonify({"status":"error","message":"Weka maudhui!"}), 400
    ann = Announcement(title=request.form.get('title','').strip(), body=body,
        position=request.form.get('position','inside'), style=request.form.get('style','info'))
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename:
            ext = f.filename.rsplit('.',1)[-1].lower()
            if ext in ['jpg','jpeg','png','gif','webp']:
                fn = 'ann_'+uuid.uuid4().hex+'.'+ext
                f.save(os.path.join('static/uploads/pictures', fn))
                ann.image_filename = fn
    db.session.add(ann); db.session.commit()
    return jsonify({"status":"success","message":"Tangazo limeongezwa!"})

@app.route('/admin/announcements/<int:aid>/toggle', methods=['POST'])
@admin_required
def toggle_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    ann.is_active = not ann.is_active; db.session.commit()
    return jsonify({"status":"success","is_active":ann.is_active})

@app.route('/admin/announcements/<int:aid>/delete', methods=['POST'])
@admin_required
def delete_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    if ann.image_filename:
        p = os.path.join('static/uploads/pictures', ann.image_filename)
        if os.path.exists(p): os.remove(p)
    db.session.delete(ann); db.session.commit()
    return jsonify({"status":"success","message":"Tangazo limefutwa!"})

# ===================== BRANDING =====================

@app.route('/admin/branding', methods=['POST'])
@admin_required
def update_branding():
    updated = []
    if 'logo' in request.files:
        f = request.files['logo']
        if f and f.filename:
            ext = f.filename.rsplit('.',1)[-1].lower()
            if ext in ['png','jpg','jpeg','svg','webp','gif']:
                fn = 'logo.'+ext
                f.save(os.path.join('static/uploads/logos', fn))
                SiteSettings.set('logo_filename', fn); updated.append('Logo')
    for key, label in [('site_name','Jina'),('tagline','Kauli Mbiu'),('primary_color','Rangi')]:
        val = request.form.get(key,'').strip()
        if val: SiteSettings.set(key, val); updated.append(label)
    db.session.commit()
    return jsonify({"status":"success","message":f"{', '.join(updated)} imesasishwa!"} if updated else {"status":"error","message":"Hakuna mabadiliko!"})

# ===================== STATIC FILES =====================

@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route('/static/uploads/logos/<filename>')
def logo_file(filename):
    return send_from_directory('static/uploads/logos', filename)

@app.route('/static/uploads/pictures/<filename>')
def picture_file(filename):
    return send_from_directory('static/uploads/pictures', filename)

@app.route('/level_card')
@login_required
def level_card():
    user = User.query.get(session['user_id'])
    return render_template('level_card.html', user=user, vip_threshold=int(SiteSettings.get("vip_threshold", str(VIP_REFERRAL_THRESHOLD))))

# ===================== ADMIN UI EDITOR =====================

UI_KEYS = [
    'primary_color','bg_color','card_color','text_color','navbar_color',
    'font_family','font_size','border_radius','show_shadows','show_bg_pattern',
    'show_ref_code','show_transactions','navbar_title','welcome_msg'
]

@app.route('/admin/user/<int:uid>/ui')
@admin_required
def admin_ui_editor(uid):
    user = User.query.get_or_404(uid)
    raw = {s.key: s.value for s in SiteSettings.query.filter(
        SiteSettings.key.like(f'ui_{uid}_%')).all()}
    ui = {k.replace(f'ui_{uid}_', ''): v for k, v in raw.items()}
    return render_template('admin_ui_editor.html', target_user=user, ui=ui)

@app.route('/admin/user/<int:uid>/ui', methods=['POST'])
@admin_required
def save_ui(uid):
    User.query.get_or_404(uid)
    data = request.get_json()
    for key in UI_KEYS:
        val = data.get(key, '')
        SiteSettings.set(f'ui_{uid}_{key}', str(val))
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"UI ya mtumiaji imehifadhiwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route('/admin/user/<int:uid>/ui/reset', methods=['POST'])
@admin_required
def reset_ui(uid):
    User.query.get_or_404(uid)
    settings = SiteSettings.query.filter(SiteSettings.key.like(f'ui_{uid}_%')).all()
    for s in settings:
        db.session.delete(s)
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"Imerejesha mipangilio ya asili!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

# ===================== PUBLIC PAGES (kabla ya login) =====================

@app.route('/home')
def public_home():
    articles = Article.query.filter_by(is_active=True).order_by(Article.created_at.desc()).all()
    import json
    articles_json = json.dumps([{
        'id': a.id, 'title': a.title, 'category': a.category,
        'summary': a.summary or '', 'content': a.content,
        'image_filename': a.image_filename or '',
        'created_at': a.created_at.strftime('%d %b %Y')
    } for a in articles])
    user_count = User.query.filter(~User.username.like('ref_%')).count()
    return render_template('public.html',
        articles=articles,
        articles_json=articles_json,
        site_about_short=SiteSettings.get('about_short',''),
        site_about_full=SiteSettings.get('about_full',''),
        site_users_count=f"{user_count:,}+")

@app.route('/privacy')
def privacy_page():
    return redirect('/#footer')

@app.route('/terms')
def terms_page():
    return redirect('/#footer')

# ===================== ADMIN ARTICLES =====================

@app.route('/admin/articles')
@admin_required
def admin_articles():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    import json
    articles_json = json.dumps([{
        'id': a.id, 'title': a.title, 'category': a.category,
        'summary': a.summary or '', 'content': a.content,
        'image_filename': a.image_filename or ''
    } for a in articles])
    return render_template('admin_articles.html', articles=articles, articles_json=articles_json)

@app.route('/admin/articles/add', methods=['POST'])
@admin_required
def add_article():
    title = request.form.get('title','').strip()
    content = request.form.get('content','').strip()
    if not title or not content:
        return jsonify({"status":"error","message":"Weka kichwa na maudhui!"}), 400
    art = Article(
        title=title,
        category=request.form.get('category','finance'),
        summary=request.form.get('summary','').strip(),
        content=content
    )
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename:
            ext = f.filename.rsplit('.',1)[-1].lower()
            if ext in ['jpg','jpeg','png','webp','gif']:
                os.makedirs('static/uploads/articles', exist_ok=True)
                fn = 'art_' + uuid.uuid4().hex + '.' + ext
                f.save(os.path.join('static/uploads/articles', fn))
                art.image_filename = fn
    try:
        db.session.add(art)
        db.session.commit()
        return jsonify({"status":"success","message":f"Makala '{title}' imechapishwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route('/admin/articles/<int:aid>/edit', methods=['POST'])
@admin_required
def edit_article(aid):
    art = Article.query.get_or_404(aid)
    if request.form.get('title'): art.title = request.form['title'].strip()
    if request.form.get('category'): art.category = request.form['category']
    if request.form.get('summary') is not None: art.summary = request.form['summary'].strip()
    if request.form.get('content'): art.content = request.form['content'].strip()
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename:
            ext = f.filename.rsplit('.',1)[-1].lower()
            if ext in ['jpg','jpeg','png','webp','gif']:
                os.makedirs('static/uploads/articles', exist_ok=True)
                if art.image_filename:
                    old = os.path.join('static/uploads/articles', art.image_filename)
                    if os.path.exists(old): os.remove(old)
                fn = 'art_' + uuid.uuid4().hex + '.' + ext
                f.save(os.path.join('static/uploads/articles', fn))
                art.image_filename = fn
    try:
        db.session.commit()
        return jsonify({"status":"success","message":"Makala imesasishwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route('/admin/articles/<int:aid>/toggle', methods=['POST'])
@admin_required
def toggle_article(aid):
    art = Article.query.get_or_404(aid)
    art.is_active = not art.is_active
    db.session.commit()
    return jsonify({"status":"success","message":f"Makala {'imechapishwa' if art.is_active else 'imefichwa'}!"})

@app.route('/admin/articles/<int:aid>/delete', methods=['POST'])
@admin_required
def delete_article(aid):
    art = Article.query.get_or_404(aid)
    if art.image_filename:
        p = os.path.join('static/uploads/articles', art.image_filename)
        if os.path.exists(p): os.remove(p)
    try:
        db.session.delete(art)
        db.session.commit()
        return jsonify({"status":"success","message":"Makala imefutwa!"})
    except:
        db.session.rollback()
        return jsonify({"status":"error","message":"Hitilafu imetokea!"}), 500

@app.route('/static/uploads/articles/<filename>')
def article_image(filename):
    return send_from_directory('static/uploads/articles', filename)

# ===================== PWA =====================

@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory('static', 'manifest.json',
        mimetype='application/manifest+json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js',
        mimetype='application/javascript')

# ===================== STARTUP =====================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not SiteSettings.query.first():
            for k, v in [("youtube_url",""),("referral_bonus","500"),("min_withdrawal","2000"),("vip_threshold","20")]:
                db.session.add(SiteSettings(key=k, value=v))
            db.session.commit()
    app.run(debug=True, host="0.0.0.0", port=5000)
