"""
نظام سجلات التدقيق لمنصة "مسابقاتي"
يتيح تسجيل وتتبع جميع الأنشطة الحساسة في النظام
مع إمكانية تنبيه المشرفين عند اكتشاف نشاط مشبوه
"""

import logging
import json
import os
from datetime import datetime
from functools import wraps
from flask import request, current_app
from flask_login import current_user
from models import AdminNotification, User, db

# إعداد نظام التسجيل
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# التأكد من وجود مجلد للسجلات
os.makedirs('logs', exist_ok=True)

# مسار ملف السجلات
audit_log_file = 'logs/audit.log'

# إضافة معالج لكتابة السجلات في ملف
file_handler = logging.FileHandler(audit_log_file)
file_handler.setLevel(logging.INFO)

# تنسيق سجلات التدقيق
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)

# أنواع الأحداث
EVENT_TYPES = {
    'LOGIN_ATTEMPT': 'محاولة تسجيل الدخول',
    'LOGIN_SUCCESS': 'تسجيل دخول ناجح',
    'LOGIN_FAILURE': 'فشل تسجيل الدخول',
    'LOGOUT': 'تسجيل الخروج',
    'PASSWORD_CHANGE': 'تغيير كلمة المرور',
    'USER_REGISTRATION': 'تسجيل مستخدم جديد',
    'ADMIN_ACCESS': 'وصول إلى واجهة المشرف',
    'SETTINGS_CHANGE': 'تغيير إعدادات النظام',
    'POINTS_ADDITION': 'إضافة نقاط كربتو',
    'POINTS_DEDUCTION': 'خصم نقاط كربتو',
    'REWARD_REDEMPTION': 'استبدال جائزة',
    'COMPETITION_CREATION': 'إنشاء مسابقة جديدة',
    'COMPETITION_MODIFICATION': 'تعديل مسابقة',
    'REWARD_CREATION': 'إنشاء جائزة جديدة',
    'REWARD_MODIFICATION': 'تعديل جائزة',
    'USER_MODIFICATION': 'تعديل بيانات مستخدم',
    'SUSPICIOUS_ACTIVITY': 'نشاط مشبوه',
}

# مستويات الخطورة
SEVERITY_LEVELS = {
    'INFO': 'معلومات',
    'WARNING': 'تحذير',
    'ALERT': 'تنبيه',
    'CRITICAL': 'حرج',
}

def log_audit_event(event_type, severity, details=None, user_id=None, username=None, ip_address=None, notify_admin=False, related_user_id=None):
    """
    تسجيل حدث في سجل التدقيق
    
    Args:
        event_type: نوع الحدث من EVENT_TYPES
        severity: مستوى الخطورة من SEVERITY_LEVELS
        details: تفاصيل إضافية عن الحدث
        user_id: معرف المستخدم المرتبط بالحدث
        username: اسم المستخدم المرتبط بالحدث
        ip_address: عنوان IP المرتبط بالحدث
        notify_admin: هل يجب إشعار المشرفين بهذا الحدث
        related_user_id: معرف مستخدم آخر مرتبط بالحدث (مثل المستخدم الذي تم تعديل نقاطه)
    """
    # الحصول على بيانات المستخدم الحالي إذا لم يتم تمريرها
    if current_user and current_user.is_authenticated:
        user_id = user_id or current_user.id
        username = username or current_user.username
    
    # الحصول على عنوان IP إذا لم يتم تمريره
    if not ip_address and request:
        # محاولة الحصول على IP الحقيقي
        if 'X-Forwarded-For' in request.headers:
            ip_address = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        else:
            ip_address = request.remote_addr
    
    # إعداد بيانات الحدث
    event_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'event_name': EVENT_TYPES.get(event_type, event_type),
        'severity': severity,
        'severity_name': SEVERITY_LEVELS.get(severity, severity),
        'user_id': user_id,
        'username': username,
        'ip_address': ip_address,
        'details': details,
        'related_user_id': related_user_id,
        'url': request.url if request else None,
        'user_agent': request.user_agent.string if request and request.user_agent else None,
    }
    
    # تسجيل الحدث في ملف السجل
    audit_logger.info(json.dumps(event_data, ensure_ascii=False))
    
    # إنشاء إشعار للمشرفين إذا تم طلب ذلك
    if notify_admin and event_type in ['LOGIN_FAILURE', 'SUSPICIOUS_ACTIVITY', 'SETTINGS_CHANGE', 'POINTS_ADDITION', 'POINTS_DEDUCTION']:
        create_admin_notification(event_type, event_data)

def create_admin_notification(event_type, event_data):
    """
    إنشاء إشعار للمشرفين عند اكتشاف نشاط مشبوه
    
    Args:
        event_type: نوع الحدث
        event_data: بيانات الحدث
    """
    # تحضير العنوان والرسالة
    if event_type == 'LOGIN_FAILURE':
        title = 'محاولات فاشلة متكررة لتسجيل الدخول'
        message = f"تم رصد محاولات فاشلة متكررة لتسجيل الدخول من العنوان {event_data['ip_address']} للمستخدم {event_data['username'] or 'غير معروف'}"
    elif event_type == 'SUSPICIOUS_ACTIVITY':
        title = 'نشاط مشبوه'
        message = f"تم رصد نشاط مشبوه: {event_data['details'] or ''} من المستخدم {event_data['username'] or 'غير معروف'}"
    elif event_type == 'SETTINGS_CHANGE':
        title = 'تغيير إعدادات النظام'
        message = f"تم تغيير إعدادات النظام بواسطة {event_data['username'] or 'غير معروف'}: {event_data['details'] or ''}"
    elif event_type == 'POINTS_ADDITION':
        title = 'إضافة نقاط كربتو'
        message = f"تم إضافة نقاط كربتو بواسطة {event_data['username'] or 'غير معروف'}: {event_data['details'] or ''}"
    elif event_type == 'POINTS_DEDUCTION':
        title = 'خصم نقاط كربتو'
        message = f"تم خصم نقاط كربتو بواسطة {event_data['username'] or 'غير معروف'}: {event_data['details'] or ''}"
    else:
        title = f"إشعار: {EVENT_TYPES.get(event_type, event_type)}"
        message = event_data['details'] or f"إشعار جديد من نوع {EVENT_TYPES.get(event_type, event_type)}"
    
    # إنشاء الإشعار في قاعدة البيانات
    try:
        notification = AdminNotification(
            title=title,
            message=message,
            notification_type=event_type.lower(),
            related_user_id=event_data.get('user_id')
        )
        db.session.add(notification)
        db.session.commit()
        
        # تسجيل نجاح إنشاء الإشعار
        audit_logger.info(f"تم إنشاء إشعار للمشرفين: {title}")
    except Exception as e:
        # تسجيل فشل إنشاء الإشعار
        db.session.rollback()
        audit_logger.error(f"فشل في إنشاء إشعار للمشرفين: {str(e)}")

def monitor_login_attempts(username, success, ip_address, details=None):
    """
    مراقبة محاولات تسجيل الدخول واكتشاف محاولات القوة الغاشمة
    
    Args:
        username: اسم المستخدم الذي تمت محاولة تسجيل الدخول باسمه
        success: هل نجحت محاولة تسجيل الدخول
        ip_address: عنوان IP الذي تمت منه محاولة تسجيل الدخول
        details: تفاصيل إضافية
    """
    from datetime import timedelta
    from app import app
    
    # تخزين محاولات تسجيل الدخول في الجلسة
    if not hasattr(app, 'login_attempts'):
        app.login_attempts = {}
    
    # مفتاح فريد لعنوان IP
    ip_key = f"ip_{ip_address}"
    
    # مفتاح فريد لاسم المستخدم
    username_key = f"user_{username}"
    
    # الوقت الحالي
    now = datetime.utcnow()
    
    # تنظيف المحاولات القديمة (أكثر من ساعة)
    keys_to_delete = []
    for key, attempts in app.login_attempts.items():
        for attempt_time in list(attempts):
            if now - attempt_time > timedelta(hours=1):
                attempts.remove(attempt_time)
        if not attempts:
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        del app.login_attempts[key]
    
    # تسجيل محاولة جديدة
    if ip_key not in app.login_attempts:
        app.login_attempts[ip_key] = []
    app.login_attempts[ip_key].append(now)
    
    if username_key not in app.login_attempts:
        app.login_attempts[username_key] = []
    app.login_attempts[username_key].append(now)
    
    # اكتشاف محاولات القوة الغاشمة
    if not success:
        # إذا كان هناك أكثر من 5 محاولات فاشلة خلال 5 دقائق من نفس IP
        recent_ip_attempts = [t for t in app.login_attempts[ip_key] if now - t < timedelta(minutes=5)]
        if len(recent_ip_attempts) >= 5:
            log_audit_event(
                event_type='SUSPICIOUS_ACTIVITY',
                severity='ALERT',
                details=f"تم رصد {len(recent_ip_attempts)} محاولات فاشلة لتسجيل الدخول خلال 5 دقائق من نفس عنوان IP",
                username=username,
                ip_address=ip_address,
                notify_admin=True
            )
        
        # إذا كان هناك أكثر من 3 محاولات فاشلة خلال 5 دقائق لنفس اسم المستخدم
        recent_username_attempts = [t for t in app.login_attempts[username_key] if now - t < timedelta(minutes=5)]
        if len(recent_username_attempts) >= 3:
            log_audit_event(
                event_type='SUSPICIOUS_ACTIVITY',
                severity='ALERT',
                details=f"تم رصد {len(recent_username_attempts)} محاولات فاشلة لتسجيل الدخول خلال 5 دقائق لاسم المستخدم {username}",
                username=username,
                ip_address=ip_address,
                notify_admin=True
            )
    
    # تسجيل محاولة تسجيل الدخول في سجل التدقيق
    event_type = 'LOGIN_SUCCESS' if success else 'LOGIN_FAILURE'
    severity = 'INFO' if success else 'WARNING'
    log_audit_event(
        event_type=event_type,
        severity=severity,
        details=details,
        username=username,
        ip_address=ip_address,
        notify_admin=not success
    )

    # إذا كانت هناك محاولة تسجيل دخول ناجحة بعد عدة محاولات فاشلة، سجل ذلك أيضًا
    if success and username_key in app.login_attempts:
        recent_failed_attempts = len([t for t in app.login_attempts[username_key][:-1] if now - t < timedelta(minutes=30)])
        if recent_failed_attempts >= 3:
            log_audit_event(
                event_type='SUSPICIOUS_ACTIVITY',
                severity='WARNING',
                details=f"تسجيل دخول ناجح بعد {recent_failed_attempts} محاولات فاشلة خلال الـ 30 دقيقة الماضية",
                username=username,
                ip_address=ip_address,
                notify_admin=True
            )

def log_sensitive_action(action_type):
    """
    زخرفة لتسجيل الإجراءات الحساسة تلقائيًا
    
    Args:
        action_type: نوع الإجراء من EVENT_TYPES
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # الحصول على نتيجة الدالة الأصلية
            result = func(*args, **kwargs)
            
            # استخراج المعلومات من الطلب
            ip_address = request.remote_addr
            if 'X-Forwarded-For' in request.headers:
                ip_address = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            
            # استخراج معلومات المستخدم
            user_id = None
            username = None
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                username = current_user.username
            
            # تحديد مستوى الخطورة
            severity = 'INFO'
            if action_type in ['SETTINGS_CHANGE', 'POINTS_ADDITION', 'POINTS_DEDUCTION']:
                severity = 'WARNING'
            
            # تحضير التفاصيل
            details = f"تم تنفيذ {EVENT_TYPES.get(action_type, action_type)} على المسار {request.path}"
            
            # تسجيل الحدث
            log_audit_event(
                event_type=action_type,
                severity=severity,
                details=details,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                notify_admin=(action_type in ['SETTINGS_CHANGE', 'POINTS_ADDITION', 'POINTS_DEDUCTION'])
            )
            
            return result
        return wrapper
    return decorator