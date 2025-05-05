import os
import logging
from datetime import timedelta
import importlib.util
import secrets

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Configure logging
logging.basicConfig(level=logging.DEBUG)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)

# محاولة استيراد ملف الإعدادات السرية إذا كان موجوداً
config_secrets_spec = importlib.util.find_spec("config_secrets")
if config_secrets_spec is not None:
    import config_secrets
    app.logger.info("تم استيراد ملف الإعدادات السرية")
    # استخدام المفتاح السري من ملف الإعدادات إذا كان موجوداً
    app.secret_key = getattr(config_secrets, "SECRET_KEY", None)
else:
    app.logger.warning("ملف الإعدادات السرية غير موجود، يتم استخدام الإعدادات الافتراضية")

# إذا لم يتم تعيين المفتاح السري من ملف الإعدادات، استخدم المتغير البيئي أو قم بإنشاء واحد تلقائيًا
if not app.secret_key:
    app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
    if not os.environ.get("SESSION_SECRET"):
        app.logger.warning("تم إنشاء مفتاح سري عشوائي. يُرجى تعيين SESSION_SECRET أو SECRET_KEY في الإعدادات")

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# تكوين ملفات تعريف ارتباط الجلسة
app.config.update(
    SESSION_COOKIE_SECURE=True,  # يضمن استخدام HTTPS فقط
    SESSION_COOKIE_HTTPONLY=True,  # يمنع الوصول عبر JavaScript
    SESSION_COOKIE_SAMESITE='Lax',  # يحمي من هجمات CSRF عبر المواقع
    PERMANENT_SESSION_LIFETIME=timedelta(days=1)  # تعيين مدة الجلسة
)

# تكوين قاعدة البيانات
# استخدام عنوان قاعدة البيانات من ملف الإعدادات السرية إذا كان موجوداً
if config_secrets_spec is not None and hasattr(config_secrets, "DATABASE_URI"):
    app.config["SQLALCHEMY_DATABASE_URI"] = config_secrets.DATABASE_URI
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///musabaqati.db")

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة'
login_manager.login_message_category = 'info'

# تكوين حماية معدل الطلبات (Rate Limiting)
# استخدام IP الحقيقي للمستخدم حتى مع وجود reverse proxy
def get_real_ip():
    """الحصول على عنوان IP الحقيقي للمستخدم مع مراعاة reverse proxy"""
    if request and 'X-Forwarded-For' in request.headers:
        # تقسيم سلسلة العناوين واختيار أول عنصر (عنوان العميل الأصلي)
        x_forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if x_forwarded_for:
            return x_forwarded_for
    return get_remote_address()

limiter = Limiter(
    key_func=get_real_ip,  # استخدام الدالة المعرفة أعلاه 
    app=app,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://",  # يمكن استبدالها بـ Redis في بيئة الإنتاج
    strategy="fixed-window"  # استراتيجية النافذة الثابتة
)

# إضافة قيود خاصة لمسارات معينة
# سيتم تطبيقها على المسارات في ملف routes.py

# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

with app.app_context():
    # Import models
    from models import User, Competition, Reward, Participation, RewardRedemption, ChatRoom, ChatRoomMember, Message
    
    # Import routes
    from routes import *
    
    # Create all tables
    db.create_all()
    
    # Make models available in templates
    app.jinja_env.globals.update(
        ChatRoom=ChatRoom,
        ChatRoomMember=ChatRoomMember,
        Message=Message
    )
    
    # User loader callback
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
