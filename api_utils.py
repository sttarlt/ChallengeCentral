"""
واجهة برمجة التطبيقات (API) لمنصة مسابقاتي
توفر وصولًا آمنًا للبيانات والوظائف الأساسية للتطبيق
مع حماية كاملة وتوثيق للعمليات الحساسة
"""

import time
import secrets
import string
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app, abort
from flask_cors import cross_origin
from app import app, db, limiter
from models import User, APIKey, Reward, Referral, SystemConfig
from audit_log import log_audit_event, EVENT_TYPES, SEVERITY_LEVELS
import config

# إعداد التسجيل الخاص بواجهة API
api_logger = logging.getLogger('api')
api_logger.setLevel(logging.INFO)

# التأكد من وجود معالج للتسجيل في الملف
if not api_logger.handlers:
    file_handler = logging.FileHandler('logs/api.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    api_logger.addHandler(file_handler)

class APIError(Exception):
    """
    استثناء مخصص للأخطاء المتعلقة بواجهة برمجة التطبيقات
    """
    def __init__(self, message, status_code=400, payload=None):
        super().__init__(self)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        rv['status'] = 'error'
        return rv

def generate_api_key():
    """
    توليد مفتاح API عشوائي آمن
    """
    alphabet = string.ascii_letters + string.digits
    api_key = 'msb_' + ''.join(secrets.choice(alphabet) for _ in range(32))
    return api_key

def validate_api_key():
    """
    التحقق من صحة مفتاح API
    """
    # الحصول على المفتاح من رأس الطلب
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise APIError('لم يتم توفير مفتاح API', status_code=401)
    
    # تنسيق المفتاح يجب أن يكون "Bearer API_KEY"
    parts = auth_header.split()
    if parts[0].lower() != 'bearer' or len(parts) != 2:
        raise APIError('تنسيق التفويض غير صحيح', status_code=401)
    
    api_key_value = parts[1]
    
    # البحث عن المفتاح في قاعدة البيانات
    api_key = APIKey.query.filter_by(key=api_key_value, is_active=True).first()
    if not api_key:
        raise APIError('مفتاح API غير صالح', status_code=401)
    
    # التحقق من تاريخ انتهاء الصلاحية
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        api_key.is_active = False
        db.session.commit()
        raise APIError('مفتاح API منتهي الصلاحية', status_code=401)
    
    # تخزين معرف المستخدم للاستخدام لاحقًا
    g.user_id = api_key.user_id
    g.api_key_id = api_key.id
    
    # تحديث آخر استخدام
    api_key.last_used_at = datetime.utcnow()
    api_key.usage_count += 1
    db.session.commit()
    
    return True

def require_api_key(f):
    """
    زخرفة للتأكد من أن الطلب يحتوي على مفتاح API صالح
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            validate_api_key()
        except APIError as e:
            return jsonify(e.to_dict()), e.status_code
        return f(*args, **kwargs)
    return decorated

def api_rate_limit(limit_string="30 per minute"):
    """
    زخرفة لتطبيق الحد من معدل الطلبات حسب مفتاح API والعنوان IP
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # تطبيق الحد من معدل الطلبات
            @limiter.limit(limit_string, key_func=lambda: request.headers.get('Authorization', '') + request.remote_addr)
            def rate_limited_function(*args, **kwargs):
                return f(*args, **kwargs)
            return rate_limited_function(*args, **kwargs)
        return decorated_function
    return decorator

def get_api_config():
    """
    الحصول على إعدادات API من قاعدة البيانات أو ملف الإعدادات
    """
    # البحث عن إعدادات CORS في قاعدة البيانات
    allowed_origins = None
    try:
        config_record = SystemConfig.query.filter_by(key='API_ALLOWED_ORIGINS').first()
        if config_record and config_record.value:
            allowed_origins = config_record.value.split(',')
    except Exception as e:
        api_logger.error(f"خطأ في الحصول على إعدادات API: {str(e)}")
    
    # إذا لم يتم العثور على قيمة، استخدم القيمة الافتراضية من ملف الإعدادات
    if not allowed_origins:
        allowed_origins = getattr(config, 'API_ALLOWED_ORIGINS', ['*'])
    
    return {
        'allowed_origins': allowed_origins
    }

def log_api_call(endpoint, status_code, user_id=None, details=None):
    """
    تسجيل طلب API في سجل التدقيق
    """
    try:
        # الحصول على معلومات الطلب
        method = request.method
        path = request.path
        ip_address = request.remote_addr
        user_agent = request.user_agent.string if request.user_agent else "غير معروف"
        
        # تجميع التفاصيل
        log_details = {
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        # إضافة التفاصيل المخصصة إذا تم توفيرها
        if details:
            log_details.update(details)
        
        # تسجيل الحدث في سجل التدقيق
        severity = SEVERITY_LEVELS['INFO'] if 200 <= status_code < 400 else SEVERITY_LEVELS['WARNING']
        log_audit_event(
            event_type=EVENT_TYPES['API_ACCESS'],
            severity=severity,
            details=str(log_details),
            user_id=user_id,
            ip_address=ip_address,
            notify_admin=(status_code >= 400)  # إشعار المشرف في حالة الأخطاء
        )
        
        # تسجيل في ملف السجل أيضًا
        if status_code >= 400:
            api_logger.warning(f"API request failed: {log_details}")
        else:
            api_logger.info(f"API request: {log_details}")
    
    except Exception as e:
        app.logger.error(f"خطأ في تسجيل طلب API: {str(e)}")

def sanitize_input(data, allowed_fields=None, max_length=None):
    """
    تنظيف وتحقق من صحة بيانات الإدخال
    
    Args:
        data: البيانات المدخلة للتحقق منها (dict)
        allowed_fields: قائمة الحقول المسموح بها (list)
        max_length: الطول الأقصى للقيم النصية (int)
    
    Returns:
        dict: البيانات بعد التنظيف
    """
    if not data:
        return {}
    
    sanitized = {}
    
    for key, value in data.items():
        # التحقق من الحقول المسموح بها
        if allowed_fields and key not in allowed_fields:
            continue
            
        # تنظيف القيم النصية
        if isinstance(value, str):
            # تقييد الطول
            if max_length and len(value) > max_length:
                value = value[:max_length]
            
            # إزالة أي أكواد HTML أو JavaScript خطيرة
            value = value.replace('<', '&lt;').replace('>', '&gt;')
            
        # إضافة القيمة المنظفة
        sanitized[key] = value
    
    return sanitized

def handle_api_error(error):
    """
    معالجة أخطاء API وإعادة استجابة متسقة
    """
    if isinstance(error, APIError):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
    else:
        app.logger.error(f"خطأ غير متوقع في API: {str(error)}")
        response = jsonify({
            'status': 'error',
            'error': 'حدث خطأ داخلي في الخادم'
        })
        response.status_code = 500
    
    try:
        # تسجيل الخطأ في سجل الأحداث
        log_api_call(
            endpoint=request.path,
            status_code=response.status_code,
            user_id=getattr(g, 'user_id', None),
            details={'error': str(error)}
        )
    except Exception as log_error:
        app.logger.error(f"خطأ أثناء تسجيل خطأ API: {str(log_error)}")
    
    return response