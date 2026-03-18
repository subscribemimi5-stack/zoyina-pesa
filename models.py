from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Aina za majukwaa (platforms) na muda wa kutazama unaohitajika
PLATFORM_CONFIG = {
    'youtube':  {'label': 'YouTube',  'icon': '▶', 'color': '#FF0000', 'bg': '#1a0000', 'min_seconds': 60,  'max_seconds': 180},
    'tiktok':   {'label': 'TikTok',   'icon': '♪', 'color': '#69C9D0', 'bg': '#001a1b', 'min_seconds': 60,  'max_seconds': 60},
    'facebook': {'label': 'Facebook', 'icon': 'f', 'color': '#1877F2', 'bg': '#00091a', 'min_seconds': 90,  'max_seconds': 120},
    'instagram':{'label': 'Instagram','icon': '◈', 'color': '#E1306C', 'bg': '#1a0010', 'min_seconds': 60,  'max_seconds': 90},
    'twitter':  {'label': 'Twitter/X','icon': '✕', 'color': '#1DA1F2', 'bg': '#001526', 'min_seconds': 45,  'max_seconds': 90},
    'other':    {'label': 'Nyingine', 'icon': '◉', 'color': '#00C853', 'bg': '#001a08', 'min_seconds': 30,  'max_seconds': 60},
}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    password_plain = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    referral_code = db.Column(db.String(20), unique=True)
    referred_by = db.Column(db.String(20))
    balance = db.Column(db.Float, default=0.0)
    total_earned = db.Column(db.Float, default=0.0)
    ip_address = db.Column(db.String(45), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_subscribed = db.Column(db.Boolean, default=False)
    level = db.Column(db.Integer, default=1)
    can_view_ads = db.Column(db.Boolean, default=False)
    # ── Bot protection fields ──
    login_attempts = db.Column(db.Integer, default=0)           # Idadi ya majaribio ya kuingia yaliyoshindwa
    locked_until = db.Column(db.DateTime, nullable=True)        # Akaunti imefungwa hadi wakati huu
    last_login_at = db.Column(db.DateTime, nullable=True)       # Mara ya mwisho kuingia

    @property
    def referral_count(self):
        return User.query.filter_by(referred_by=self.referral_code).count()

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    amount = db.Column(db.Float)
    transaction_type = db.Column(db.String(20))
    description = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", backref="transactions")

class AdGroup(db.Model):
    """Kikundi cha matangazo — mfano: 'YouTube Ads', 'TikTok Ads'"""
    __tablename__ = 'ad_group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)          # Jina la kikundi
    platform = db.Column(db.String(20), default='other')      # youtube/tiktok/facebook/instagram/twitter/other
    description = db.Column(db.String(500))
    watch_seconds = db.Column(db.Integer, default=60)         # Muda wa kutazama unaohitajika (sekunde)
    reward_per_ad = db.Column(db.Float, default=500.0)        # Malipo kwa kila tangazo
    min_level = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ads = db.relationship('Advertisement', backref='group', lazy=True, cascade='all, delete-orphan')

    @property
    def platform_config(self):
        from models import PLATFORM_CONFIG
        return PLATFORM_CONFIG.get(self.platform, PLATFORM_CONFIG['other'])

    @property
    def active_ads_count(self):
        return Advertisement.query.filter_by(group_id=self.id, is_active=True).count()

class Advertisement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('ad_group.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    platform = db.Column(db.String(20), default='other')      # platform ya tangazo hili
    video_type = db.Column(db.String(10), default='url')      # url / file
    video_url = db.Column(db.String(500))
    video_filename = db.Column(db.String(300))
    watch_seconds = db.Column(db.Integer, default=60)         # override ya kikundi
    min_level = db.Column(db.Integer, default=1)
    reward = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    order_num = db.Column(db.Integer, default=0)              # mpangilio ndani ya kikundi
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def platform_config(self):
        from models import PLATFORM_CONFIG
        return PLATFORM_CONFIG.get(self.platform, PLATFORM_CONFIG['other'])

class AdView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ad_id = db.Column(db.Integer, db.ForeignKey('advertisement.id'), nullable=False)
    reward = db.Column(db.Float, default=0.0)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='ad_views')
    ad = db.relationship('Advertisement', backref='views')

class UserGroupProgress(db.Model):
    """Kufuatilia maendeleo ya mtumiaji kwenye kikundi — ametazama kiasi gani"""
    __tablename__ = 'user_group_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('ad_group.id'), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)      # wakati alipokamilisha kikundi chote
    date_key = db.Column(db.String(10), nullable=False)       # YYYY-MM-DD — siku ya kukamilisha
    user = db.relationship('User', backref='group_progress')
    group = db.relationship('AdGroup', backref='user_progress')

class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(1000))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def get(cls, key, default=""):
        s = cls.query.filter_by(key=key).first()
        return s.value if s else default

    @classmethod
    def set(cls, key, value):
        s = cls.query.filter_by(key=key).first()
        if s:
            s.value = value
            s.updated_at = datetime.utcnow()
        else:
            s = cls(key=key, value=value)
            db.session.add(s)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50), default='Admin')
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient_type = db.Column(db.String(10), default='single')
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipient = db.relationship('User', backref='messages', foreign_keys=[recipient_id])

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    position = db.Column(db.String(20), default='inside')
    style = db.Column(db.String(20), default='info')
    image_filename = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RateLimit(db.Model):
    """Kuhesabu maombi kwa kila IP — kuzuia bots na brute-force"""
    __tablename__ = 'rate_limit'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    action = db.Column(db.String(30), nullable=False)   # 'register' / 'login'
    count = db.Column(db.Integer, default=1)
    window_start = db.Column(db.DateTime, default=datetime.utcnow)
    blocked_until = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('ip_address', 'action', name='uq_ip_action'),)

    @classmethod
    def check_and_increment(cls, ip, action, max_per_window=5, window_minutes=15, block_minutes=60):
        """Rudisha (allowed: bool, retry_after_seconds: int)."""
        from datetime import timedelta
        now = datetime.utcnow()
        rec = cls.query.filter_by(ip_address=ip, action=action).first()

        if rec:
            # Angalia kama bado imefungwa
            if rec.blocked_until and rec.blocked_until > now:
                secs = int((rec.blocked_until - now).total_seconds())
                return False, secs
            # Dirisha jipya — rejesha kaunti
            window_age = (now - rec.window_start).total_seconds() / 60
            if window_age > window_minutes:
                rec.count = 1
                rec.window_start = now
                rec.blocked_until = None
            else:
                rec.count += 1
                if rec.count > max_per_window:
                    rec.blocked_until = now + timedelta(minutes=block_minutes)
                    db.session.commit()
                    return False, block_minutes * 60
        else:
            rec = cls(ip_address=ip, action=action, count=1, window_start=now)
            db.session.add(rec)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return True, 0

class Article(db.Model):
    """Makala za ukurasa wa umma (/home)"""
    __tablename__ = 'article'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='finance')
    summary = db.Column(db.String(500))
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Article {self.title}>'
