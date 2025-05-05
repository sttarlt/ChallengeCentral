"""
واجهة برمجة التطبيقات (API) لمنصة مسابقاتي
توفر وصولًا آمنًا للبيانات والوظائف الأساسية للتطبيق
مع حماية كاملة وتوثيق للعمليات الحساسة
"""

import time
import secrets
import string
import logging
import ipaddress
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app, abort
from flask_cors import cross_origin
from app import app, db, limiter
from models import User, APIKey, Reward, Referral, SystemConfig, APIFailedAuth, APIUsageLog
from audit_log import log_audit_event, EVENT_TYPES, SEVERITY_LEVELS
import config


def get_client_ip():
    """
    الحصول على عنوان IP الحقيقي للعميل بشكل آمن
    مع مراعاة الوسطاء والشبكات العكسية
    
    عودة:
        العنوان IP الحقيقي للمستخدم
    """
    if 'X-Forwarded-For' in request.headers:
        # تقسيم سلسلة العناوين واختيار أول عنصر (عنوان العميل الأصلي)
        x_forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if x_forwarded_for:
            # التحقق من صحة تنسيق IP (تحقق بسيط)
            if len(x_forwarded_for) <= 45:  # الحد الأقصى لطول IPv6
                return x_forwarded_for
    
    # إذا لم يكن هناك X-Forwarded-For، استخدم remote_addr
    return request.remote_addr

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
    التحقق من صحة مفتاح API مع ميزات أمان إضافية
    التحقق الفوري من الإلغاء والتحديثات في الوقت الحقيقي
    """
    # الحصول على المفتاح من رأس الطلب
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        log_failed_auth_attempt(None, "no_auth_header", request.remote_addr)
        raise APIError('لم يتم توفير مفتاح API', status_code=401)
    
    # تنسيق المفتاح يجب أن يكون "Bearer API_KEY"
    parts = auth_header.split()
    if parts[0].lower() != 'bearer' or len(parts) != 2:
        log_failed_auth_attempt(None, "invalid_auth_format", request.remote_addr)
        raise APIError('تنسيق التفويض غير صحيح', status_code=401)
    
    api_key_value = parts[1]
    
    # التحقق من تنسيق المفتاح (للتحقق السريع قبل استعلام قاعدة البيانات)
    if not api_key_value.startswith('msb_') or len(api_key_value) < 20:
        log_failed_auth_attempt(None, "invalid_key_format", request.remote_addr)
        raise APIError('تنسيق مفتاح API غير صالح', status_code=401)
    
    # استخراج بادئة المفتاح للبحث السريع
    key_prefix = api_key_value[:12] if len(api_key_value) >= 12 else api_key_value
    
    # الحصول على قائمة المفاتيح الملغاة من الكاش (إن وجدت)
    # قراءة من السيستم كونفيج مع تجديد الكاش كل دقيقة
    global_revocation_timestamp = SystemConfig.get('global_revocation_timestamp')
    
    try:
        # البحث عن المفاتيح المحتملة باستخدام البادئة
        potential_keys = APIKey.query.filter_by(key_prefix=key_prefix).all()
        
        if not potential_keys:
            log_failed_auth_attempt(None, "key_not_found", request.remote_addr, key_prefix=key_prefix)
            raise APIError('مفتاح API غير صالح', status_code=401)
        
        # فحص كل مفتاح محتمل للتحقق من تطابقه مع القيمة المشفرة
        valid_key = None
        for key in potential_keys:
            # مقارنة بمقاومة لهجمات التوقيت
            if APIKey.verify_key(api_key_value, key.key_hash):
                valid_key = key
                break
        
        if not valid_key:
            log_failed_auth_attempt(None, "invalid_key_hash", request.remote_addr, key_prefix=key_prefix)
            raise APIError('مفتاح API غير صالح', status_code=401)
        
        # تحقق إضافي للإلغاء والنشاط (بعد التعرف على المفتاح)
        # التحقق من أن المفتاح نشط
        if not valid_key.is_active:
            log_failed_auth_attempt(valid_key.user_id, "inactive_key", request.remote_addr, key_id=valid_key.id)
            raise APIError('مفتاح API غير نشط', status_code=401)
        
        # التحقق من أن المفتاح غير ملغي
        if valid_key.is_revoked:
            reason = valid_key.revocation_reason or "مفتاح ملغي"
            log_failed_auth_attempt(valid_key.user_id, "revoked_key", request.remote_addr, key_id=valid_key.id, reason=reason)
            raise APIError(f'مفتاح API ملغى: {reason}', status_code=401)
        
        # التحقق من تاريخ انتهاء الصلاحية
        if valid_key.expires_at and valid_key.expires_at < datetime.utcnow():
            valid_key.is_active = False
            valid_key.is_revoked = True
            valid_key.revocation_reason = "انتهت صلاحية المفتاح"
            db.session.commit()
            log_failed_auth_attempt(valid_key.user_id, "expired_key", request.remote_addr, key_id=valid_key.id)
            raise APIError('مفتاح API منتهي الصلاحية', status_code=401)
        
        # تخزين معرف المستخدم والمفتاح للاستخدام لاحقًا
        g.user_id = valid_key.user_id
        g.api_key_id = valid_key.id
        g.api_key_permissions = valid_key.permissions
        
        # الحصول على عنوان IP الحقيقي (مع مراعاة وجود وسيط عكسي)
        client_ip = get_client_ip()
        request_user_agent = request.headers.get('User-Agent', '')
        
        # كشف الاستخدام الآلي (على سبيل المثال عبر curl أو أدوات البرمجة)
        is_automated = detect_automation(request_user_agent)
        if is_automated and valid_key.automation_detected is False:
            valid_key.automation_detected = True
            
        # كشف وتسجيل استخدام المفتاح من عنوان IP جديد
        is_new_ip = False
        if valid_key.last_ip and valid_key.last_ip != client_ip:
            is_new_ip = True
            app.logger.info(f"استخدام مفتاح API من عنوان IP جديد. المفتاح: {valid_key.id}, المستخدم: {valid_key.user_id}, IP: {client_ip}, IP سابق: {valid_key.last_ip}")
        
        # تحديث معلومات الاستخدام
        valid_key.last_used_at = datetime.utcnow()
        valid_key.usage_count += 1
        valid_key.last_ip = client_ip
        
        # تسجيل السلوك المشبوه إذا تم اكتشافه
        suspicious_behavior = detect_suspicious_usage(valid_key, is_new_ip, is_automated)
        if suspicious_behavior:
            valid_key.suspicious_activity = True
            app.logger.warning(f"تم اكتشاف نشاط مشبوه. المفتاح: {valid_key.id}, المستخدم: {valid_key.user_id}, السبب: {suspicious_behavior}")
            
            # إنشاء إشعار للمشرف إذا لزم الأمر
            if suspicious_behavior in ['multiple_ips', 'high_frequency']:
                from models import AdminNotification
                notification = AdminNotification(
                    title="نشاط مشبوه في استخدام API",
                    message=f"تم اكتشاف نشاط مشبوه في استخدام مفتاح API للمستخدم {valid_key.user_id}. السبب: {suspicious_behavior}",
                    notification_type="api_suspicious",
                    related_user_id=valid_key.user_id
                )
                db.session.add(notification)
        
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ أثناء التحقق من مفتاح API: {str(e)}")
        # إرجاع خطأ عام في حالة وجود استثناء غير متوقع
        raise APIError('حدث خطأ أثناء التحقق من المفتاح', status_code=500)


def log_failed_auth_attempt(user_id, reason, ip_address, key_id=None, key_prefix=None):
    """تسجيل محاولات المصادقة الفاشلة للكشف عن هجمات القوة الغاشمة"""
    try:
        # تسجيل المحاولة في جدول يمكن استخدامه لتتبع المحاولات المتكررة
        from models import APIFailedAuth
        
        failed_attempt = APIFailedAuth(
            user_id=user_id,
            ip_address=ip_address,
            reason=reason,
            api_key_id=key_id,
            key_prefix=key_prefix
        )
        db.session.add(failed_attempt)
        db.session.commit()
        
        # التحقق من وجود محاولات متكررة من نفس العنوان
        recent_attempts = APIFailedAuth.query.filter_by(
            ip_address=ip_address
        ).filter(
            APIFailedAuth.created_at >= datetime.utcnow() - timedelta(minutes=10)
        ).count()
        
        # إذا تجاوز العتبة، قم بتسجيل تحذير
        if recent_attempts >= 5:
            app.logger.warning(f"محاولات مصادقة فاشلة متكررة من العنوان {ip_address}: {recent_attempts} محاولات في 10 دقائق.")
            
            # يمكن إضافة تطبيق حظر مؤقت هنا
            
    except Exception as e:
        app.logger.error(f"خطأ أثناء تسجيل محاولة المصادقة الفاشلة: {str(e)}")
        db.session.rollback()


def detect_automation(user_agent):
    """الكشف عما إذا كان الطلب آلي (من أداة برمجية أو سكريبت)"""
    automation_indicators = [
        'curl', 'wget', 'python', 'requests', 'axios', 'http-client', 'postman',
        'java', 'go-http', 'ruby', 'perl', 'php', 'bot', 'crawler', 'script'
    ]
    
    user_agent = user_agent.lower()
    for indicator in automation_indicators:
        if indicator in user_agent:
            return True
            
    # تحقق من الخصائص المميزة للمتصفحات الشائعة
    browser_indicators = ['chrome', 'firefox', 'safari', 'edge', 'opera']
    has_browser_indicator = any(b in user_agent for b in browser_indicators)
    
    # افترض أنه استخدام آلي إذا لم يكن متصفحًا معروفًا وكان user-agent قصيرًا
    if not has_browser_indicator and len(user_agent) < 50:
        return True
        
    return False


def detect_suspicious_usage(api_key, is_new_ip, is_automated):
    """الكشف عن الاستخدام المشبوه للمفتاح"""
    try:
        now = datetime.utcnow()
        
        # 1. استخدام المفتاح من عناوين IP متعددة في فترة قصيرة
        if is_new_ip:
            recent_usage = db.session.query(
                APIUsageLog
            ).filter(
                APIUsageLog.api_key_id == api_key.id,
                APIUsageLog.timestamp >= now - timedelta(hours=1)
            ).group_by(
                APIUsageLog.ip_address
            ).count()
            
            if recent_usage >= 3:  # 3 عناوين IP مختلفة في ساعة واحدة
                return 'multiple_ips'
        
        # 2. معدل استخدام مرتفع في فترة قصيرة
        recent_calls = db.session.query(
            APIUsageLog
        ).filter(
            APIUsageLog.api_key_id == api_key.id,
            APIUsageLog.timestamp >= now - timedelta(minutes=1)
        ).count()
        
        if recent_calls >= 30:  # 30 طلبًا في دقيقة واحدة
            return 'high_frequency'
        
        return None
    except Exception as e:
        app.logger.error(f"خطأ أثناء الكشف عن الاستخدام المشبوه: {str(e)}")
        return None


def revoke_api_key(key_id, reason=None, permanent=False):
    """
    إلغاء مفتاح API بشكل فوري مع تحديث آلية التتبع العالمية
    """
    try:
        key = APIKey.query.get(key_id)
        if not key:
            return False, "مفتاح غير موجود"
        
        if permanent:
            # حذف المفتاح نهائيًا من قاعدة البيانات
            db.session.delete(key)
        else:
            # تعليم المفتاح كملغي فقط
            key.is_active = False
            key.is_revoked = True
            key.revocation_reason = reason
        
        # تحديث طابع زمني عالمي للإلغاء للتحقق الفوري من الإلغاء
        # هذا يسمح بالتحقق السريع من تغييرات الإلغاء الحديثة دون الحاجة إلى استعلام
        # قاعدة البيانات في كل طلب
        now = datetime.utcnow()
        SystemConfig.set(
            'global_revocation_timestamp', 
            now.isoformat(),
            'آخر وقت تم فيه إلغاء مفتاح API'
        )
        
        # إضافة المفتاح إلى قائمة المفاتيح الملغاة مؤخرًا
        recent_revocations = SystemConfig.get('recent_revoked_keys', '[]')
        try:
            revoked_keys = json.loads(recent_revocations)
            # إضافة المفتاح الجديد
            revoked_keys.append({
                'key_id': key_id,
                'revoked_at': now.isoformat(),
                'reason': reason
            })
            # الاحتفاظ بآخر 100 مفتاح فقط لمنع نمو القائمة بشكل غير محدود
            if len(revoked_keys) > 100:
                revoked_keys = revoked_keys[-100:]
            # تحديث القائمة في قاعدة البيانات
            SystemConfig.set(
                'recent_revoked_keys',
                json.dumps(revoked_keys),
                'قائمة بأحدث المفاتيح الملغاة للتحقق السريع'
            )
        except Exception as e:
            app.logger.error(f"خطأ في تحديث قائمة المفاتيح الملغاة: {str(e)}")
        
        # تسجيل الحدث في سجل التدقيق
        log_audit_event(
            EVENT_TYPES.API_KEY_REVOKED,
            f"تم إلغاء مفتاح API (ID: {key_id}) للمستخدم {key.user_id}. السبب: {reason}",
            user_id=getattr(g, 'user_id', None),
            related_id=key_id,
            severity=SEVERITY_LEVELS.MEDIUM
        )
        
        db.session.commit()
        app.logger.info(f"تم إلغاء مفتاح API (ID: {key_id}). السبب: {reason}, دائم: {permanent}")
        return True, "تم إلغاء المفتاح بنجاح"
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ أثناء إلغاء مفتاح API: {str(e)}")
        return False, f"حدث خطأ: {str(e)}"

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


def require_admin_verification(f):
    """
    زخرفة لمطالبة المستخدم بتأكيد إضافي للعمليات الحساسة
    يجب استخدام رأس X-Admin-Verification مع رمز تأكيد صالح
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # 1. التحقق من أن المستخدم مسؤول
            user_id = getattr(g, 'user_id', None)
            if not user_id:
                raise APIError("التحقق مطلوب", status_code=401)
            
            # 2. الحصول على رمز التحقق من رأس الطلب
            verification_token = request.headers.get('X-Admin-Verification')
            if not verification_token:
                raise APIError("رمز التحقق مطلوب للعمليات الحساسة", status_code=403)
            
            # 3. التحقق من صحة الرمز في قاعدة البيانات
            validation_result = validate_admin_verification_token(user_id, verification_token)
            if not validation_result:
                raise APIError("رمز التحقق غير صالح أو منتهي الصلاحية", status_code=403)
            
            # 4. تسجيل الحدث
            log_audit_event(
                EVENT_TYPES.SENSITIVE_OPERATION,
                f"تم التحقق من عملية حساسة بواسطة المستخدم {user_id}",
                user_id=user_id,
                severity=SEVERITY_LEVELS.MEDIUM
            )
            
            # 5. المتابعة مع الدالة إذا كان التحقق ناجحًا
            return f(*args, **kwargs)
            
        except APIError as e:
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            app.logger.error(f"خطأ في التحقق من العملية الحساسة: {str(e)}")
            return jsonify({
                'status': 'error',
                'error': 'حدث خطأ أثناء التحقق من العملية'
            }), 500
            
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

def get_real_ip():
    """
    الحصول على عنوان IP الحقيقي للعميل مع مراعاة وجود وسيط عكسي
    يتحقق من رؤوس الطلب المختلفة ويتأكد من صحة عنوان IP
    """
    # قائمة الشبكات الموثوقة (الوسطاء المعروفون)
    trusted_proxy_networks = [
        '10.0.0.0/8',      # خاص - شبكة فئة A
        '172.16.0.0/12',   # خاص - شبكة فئة B
        '192.168.0.0/16',  # خاص - شبكة فئة C
        '127.0.0.0/8',     # شبكة محلية
        '169.254.0.0/16',  # APIPA
        'fc00::/7',        # عناوين IPv6 الخاصة
        '::1/128',         # عنوان محلي IPv6
    ]
    
    # التحقق مما إذا كان عنوان IP يقع ضمن شبكة موثوقة
    def is_trusted_proxy(ip):
        try:
            client_ip = ipaddress.ip_address(ip)
            for network in trusted_proxy_networks:
                if client_ip in ipaddress.ip_network(network, strict=False):
                    return True
            return False
        except ValueError:
            return False  # عنوان IP غير صالح
    
    # عنوان IP الافتراضي (مباشر من العميل)
    client_ip = request.remote_addr
    
    # رؤوس الطلب التي قد تحتوي على عنوان IP الحقيقي
    # نفحص من المصادر الأكثر موثوقية
    if request.headers.get('X-Real-IP') and is_trusted_proxy(client_ip):
        proposed_ip = request.headers.get('X-Real-IP').strip()
        try:
            # التحقق من صحة صياغة عنوان IP
            ipaddress.ip_address(proposed_ip)
            return proposed_ip
        except ValueError:
            pass
    
    # فحص X-Forwarded-For (قد يحتوي على قائمة من عناوين IP)
    if request.headers.get('X-Forwarded-For') and is_trusted_proxy(client_ip):
        # الحصول على أول عنوان في القائمة (العميل الأصلي)
        forwarded_ips = request.headers.get('X-Forwarded-For').split(',')
        if forwarded_ips:
            proposed_ip = forwarded_ips[0].strip()
            try:
                ipaddress.ip_address(proposed_ip)
                return proposed_ip
            except ValueError:
                pass
    
    # استخدام عنوان IP المباشر إذا لم نتمكن من العثور على عنوان أفضل
    return client_ip


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

def require_admin_verification(f):
    """
    زخرفة للتحقق من المستخدم للعمليات الإدارية الحساسة
    تتطلب إرسال رمز تحقق إضافي مع الطلب من المسؤول
    يزيد من أمان العمليات الحساسة ويمنع الوصول غير المصرح به
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            # 1. التحقق من أن المستخدم مسؤول
            user_id = getattr(g, 'user_id', None)
            if not user_id:
                raise APIError('يجب تسجيل الدخول أولاً للوصول لهذه الخدمة', status_code=401)
                
            # التحقق من صلاحيات المستخدم
            user = User.query.get(user_id)
            if not user or not user.is_admin:
                # تسجيل محاولة وصول غير مصرح بها
                log_audit_event(
                    event_type="UNAUTHORIZED_ACCESS",
                    user_id=user_id,
                    details=f"محاولة وصول غير مصرح به لعملية إدارية حساسة: {request.path}",
                    severity="CRITICAL",
                    ip_address=get_client_ip()
                )
                raise APIError('ليس لديك صلاحية للقيام بهذه العملية الإدارية', status_code=403)
                
            # 2. التحقق من توفر رمز التحقق في رأس الطلب
            verification_token = request.headers.get('X-Admin-Verification')
            if not verification_token:
                raise APIError('العملية تتطلب تأكيد إضافي. يرجى توفير رمز التحقق في رأس الطلب', status_code=401)
                
            # 3. التحقق من صحة رمز التحقق بطريقتين
            is_valid = False
            
            # 3.1 التحقق من كلمة المرور (يمكن استخدام كلمة المرور كرمز تحقق)
            from werkzeug.security import check_password_hash
            if user.password_hash and check_password_hash(user.password_hash, verification_token):
                is_valid = True
                
            # 3.2 التحقق من الرمز المؤقت المخزن في قاعدة البيانات
            if not is_valid:
                # استرداد رمز التحقق المشفر من قاعدة البيانات
                token_key = f"admin_verification_token_{user_id}"
                token_config = SystemConfig.query.filter_by(key=token_key).first()
                
                if token_config and token_config.value:
                    # التحقق من تطابق الرمز
                    if check_password_hash(token_config.value, verification_token):
                        # التحقق من صلاحية الرمز (يجب أن يكون حديثًا - أقل من 10 دقائق)
                        timestamp_key = f"admin_verification_timestamp_{user_id}"
                        timestamp_config = SystemConfig.query.filter_by(key=timestamp_key).first()
                        
                        if timestamp_config and timestamp_config.value:
                            try:
                                token_time = datetime.fromisoformat(timestamp_config.value)
                                if (datetime.utcnow() - token_time).total_seconds() < 600:  # 10 دقائق
                                    is_valid = True
                                    
                                    # حذف الرمز بعد الاستخدام (يستخدم مرة واحدة فقط)
                                    # هذا يمنع إعادة استخدام نفس الرمز
                                    db.session.delete(token_config)
                                    db.session.delete(timestamp_config)
                                    db.session.commit()
                                else:
                                    raise APIError('انتهت صلاحية رمز التحقق، يرجى طلب رمز جديد', status_code=401)
                            except (ValueError, TypeError):
                                app.logger.error(f"تنسيق غير صالح لوقت إنشاء الرمز: {timestamp_config.value}")
                    
            if not is_valid:
                # تسجيل محاولة فاشلة
                log_audit_event(
                    event_type="FAILED_VERIFICATION",
                    user_id=user_id,
                    details=f"محاولة تحقق فاشلة لعملية حساسة - الطلب: {request.path}",
                    severity="ALERT",
                    ip_address=get_client_ip() if 'get_client_ip' in globals() else request.remote_addr
                )
                
                app.logger.warning(f"محاولة تحقق فاشلة لعملية حساسة: المستخدم {user_id}, الطلب: {request.path}")
                raise APIError('رمز التحقق غير صالح أو منتهي الصلاحية', status_code=401)
                
            # تسجيل نجاح التحقق
            log_audit_event(
                event_type="ADMIN_VERIFICATION_SUCCESS",
                user_id=user_id,
                details=f"تحقق ناجح لعملية حساسة - الطلب: {request.path}",
                severity="INFO",
                ip_address=get_client_ip() if 'get_client_ip' in globals() else request.remote_addr
            )
            
            app.logger.info(f"تحقق ناجح لعملية حساسة: المستخدم {user_id}, الطلب: {request.path}")
            
            # تنفيذ الدالة الأصلية بعد نجاح التحقق
            return f(*args, **kwargs)
            
        except APIError as e:
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            app.logger.error(f"خطأ في التحقق من المسؤول: {str(e)}")
            return jsonify({
                'status': 'error',
                'error': 'حدث خطأ أثناء التحقق من الصلاحيات'
            }), 500
    return decorated


def generate_admin_verification_token(user_id):
    """
    توليد رمز تحقق مؤقت للمسؤول
    يمكن استخدامه للتحقق من هوية المسؤول في العمليات الحساسة
    """
    # التأكد من أن المستخدم مسؤول
    user = User.query.get(user_id)
    if not user or not user.is_admin:
        raise APIError('ليس لديك صلاحية لتوليد رمز التحقق', status_code=403)
    
    # توليد رمز عشوائي قوي (16 خانة)
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    # تشفير الرمز (باستخدام نفس طريقة تشفير كلمات المرور)
    from werkzeug.security import generate_password_hash
    token_hash = generate_password_hash(token)
    
    # تخزين الرمز المشفر في قاعدة البيانات
    # استخدام SystemConfig لتخزين رموز التحقق
    token_key = f"admin_verification_token_{user_id}"
    
    # التحقق مما إذا كان هناك إعداد موجود بالفعل
    token_config = SystemConfig.query.filter_by(key=token_key).first()
    
    if token_config:
        # تحديث القيمة والوقت
        token_config.value = token_hash
        token_config.updated_at = datetime.utcnow()
    else:
        # إنشاء قيمة جديدة
        token_config = SystemConfig(
            key=token_key,
            value=token_hash,
            description="رمز التحقق المؤقت للمسؤول",
            is_public=False
        )
        db.session.add(token_config)
    
    # تخزين وقت إنشاء الرمز
    timestamp_key = f"admin_verification_timestamp_{user_id}"
    timestamp_config = SystemConfig.query.filter_by(key=timestamp_key).first()
    
    if timestamp_config:
        timestamp_config.value = datetime.utcnow().isoformat()
        timestamp_config.updated_at = datetime.utcnow()
    else:
        timestamp_config = SystemConfig(
            key=timestamp_key,
            value=datetime.utcnow().isoformat(),
            description="وقت إنشاء رمز التحقق للمسؤول",
            is_public=False
        )
        db.session.add(timestamp_config)
    
    # حفظ التغييرات
    try:
        db.session.commit()
        
        # تسجيل الحدث
        log_audit_event(
            event_type="ADMIN_VERIFICATION",
            user_id=user_id,
            details="تم توليد رمز تحقق جديد للمستخدم المسؤول",
            severity="INFO"
        )
        
        # في بيئة إنتاجية، يمكن إرسال الرمز عبر البريد الإلكتروني أو رسالة نصية
        # إلى المسؤول بدلاً من إرجاعه مباشرة
        return token
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ في حفظ رمز التحقق: {str(e)}")
        raise APIError("حدث خطأ أثناء إنشاء رمز التحقق", status_code=500)


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