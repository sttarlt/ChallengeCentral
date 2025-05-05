import os
import logging
from datetime import timedelta
import importlib.util
import secrets

from flask import Flask, request, redirect, current_app
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


# دالة تنفذ بعد كل طلب لإضافة رؤوس الأمان
def add_security_headers(response):
    """
    إضافة رؤوس أمان HTTP إلى كل استجابة
    تطبيق أفضل الممارسات الأمنية لحماية المستخدمين
    
    Arguments:
        response: كائن استجابة Flask
    Returns:
        استجابة معززة برؤوس أمان إضافية
    """
    # إضافة رؤوس HTTPS فقط في بيئة الإنتاج
    # تطبق دائمًا في وضع غير التصحيح
    if not current_app.debug and not current_app.testing:
        # رأس HSTS لفرض HTTPS مع فترة صلاحية سنة (31536000 ثانية)
        # شامل النطاقات الفرعية لتغطية جميع الخوادم الفرعية
        # تفعيل preload للتضمين في قوائم preload للمتصفحات الرئيسية
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    
    # رؤوس أمان أساسية - تطبق في جميع البيئات
    
    # منع المتصفح من تخمين أنواع MIME (مهم للوقاية من الثغرات المتعلقة بنوع المحتوى)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    # منع تضمين الموقع في إطارات خارجية لمنع هجمات الـ clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # تشغيل فلتر XSS المدمج في المتصفح مع وضع الحظر (لدعم المتصفحات القديمة)
    # ملاحظة: هذا الرأس مهمل في المتصفحات الحديثة لصالح CSP، لكن يبقى مفيدًا للمتصفحات القديمة
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    # التحكم في كيفية إرسال معلومات الإحالة عند التنقل من موقعنا لمواقع أخرى
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # رأس Feature-Policy للتحكم في ميزات المتصفح المتاحة للموقع
    # منع الوصول للميزات الحساسة مثل الميكروفون والكاميرا والموقع وغيرها
    feature_policy = "camera 'none'; microphone 'none'; geolocation 'none'; "
    feature_policy += "payment 'none'; usb 'none'; magnetometer 'none'; accelerometer 'none';"
    response.headers['Permissions-Policy'] = feature_policy
    
    # إضافة رأس Cache-Control للتحكم في تخزين الصفحات الحساسة مؤقتًا
    # منع تخزين المحتوى الديناميكي المقدم من البيانات الحساسة
    if request.path.startswith('/admin') or request.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store, max-age=0, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # سياسة أمان المحتوى (CSP) محسنة
    # تحديد المصادر المسموح بها لتحميل المحتوى
    # تقييد تشغيل البرامج النصية و CSS والوسائط من مصادر موثوقة فقط
    csp = "default-src 'self'; "
    csp += "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; " 
    csp += "style-src 'self' https://cdn.jsdelivr.net https://cdn.replit.com 'unsafe-inline'; "
    csp += "img-src 'self' data: https:; "  # السماح بالصور من مصادر HTTPS
    csp += "font-src 'self' https://cdn.jsdelivr.net https://cdn.replit.com; "
    csp += "connect-src 'self'; "  # تقييد اتصالات AJAX و WebSocket للمصدر الذاتي فقط
    csp += "frame-ancestors 'none'; "  # منع تضمين صفحاتنا في إطارات خارجية (مكافحة clickjacking)
    csp += "form-action 'self'; "  # تقييد عمليات تقديم النماذج للمصدر الذاتي فقط
    csp += "base-uri 'self'; "  # تقييد استخدام وسم <base> للمصدر الذاتي فقط
    csp += "object-src 'none';"  # منع تضمين كائنات مثل Flash و Java
    response.headers['Content-Security-Policy'] = csp
    
    return response


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

# تطبيق ميدلوير ProxyFix لدعم reverse proxy
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

# تسجيل دالة إضافة رؤوس الأمان كمعالج after_request
@app.after_request
def apply_security_headers(response):
    return add_security_headers(response)

# دالة لفرض استخدام HTTPS في الإنتاج وتطبيق إجراءات أمنية إضافية
@app.before_request
def security_checks():
    """
    تنفيذ الفحوصات الأمنية على الطلبات الواردة:
    1. فرض استخدام HTTPS في بيئة الإنتاج
    2. فحص رؤوس HTTP المشبوهة
    3. منع طلبات TRACE/TRACK (قد تستخدم في هجمات XST)
    """
    # فرض استخدام HTTPS في الإنتاج
    if not app.debug and not app.testing:
        if request.headers.get('X-Forwarded-Proto', '') != 'https':
            url = request.url.replace('http://', 'https://', 1)
            app.logger.info(f"تحويل طلب HTTP إلى HTTPS: {request.url} -> {url}")
            return redirect(url, code=301)  # إعادة توجيه دائمة
            
    # منع أساليب HTTP غير الضرورية (TRACE/TRACK) التي يمكن استغلالها في هجمات XST
    if request.method in ['TRACE', 'TRACK']:
        app.logger.warning(f"تم حظر طلب {request.method} من {request.remote_addr}")
        return '', 405  # Method Not Allowed
    
    # فحص وجود رؤوس مشبوهة (قد تشير إلى محاولات اختراق)
    suspicious_headers = [
        'X-Forwarded-Host',  # قد تستخدم لتزوير المضيف في بعض البيئات
        'X-Original-URL',    # قد تستخدم لتجاوز الحماية في بعض الخوادم
        'X-Rewrite-URL'      # مشابه لـ X-Original-URL
    ]
    
    for header in suspicious_headers:
        if header in request.headers:
            app.logger.warning(f"تم اكتشاف رأس مشبوه: {header}={request.headers[header]} من {request.remote_addr}")
            if request.path.startswith('/admin'):  # حماية إضافية للمسارات الحساسة
                return '', 403  # Forbidden
    
    # تحقق من وجود علامات هجوم في المسار (تخفيف هجمات path traversal)
    if '../' in request.path or '..\\' in request.path:
        app.logger.warning(f"تم اكتشاف محاولة path traversal في المسار: {request.path} من {request.remote_addr}")
        return '', 403  # Forbidden

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
