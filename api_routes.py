"""
واجهة برمجة التطبيقات (API) لمنصة "مسابقاتي"
نقاط النهاية المؤمنة للوصول إلى البيانات والوظائف
"""

from flask import Blueprint, jsonify, request, g, current_app, make_response
from flask_cors import CORS
import time
import json
from app import app, db
from models import User, Reward, Referral, APIKey, PointsTransaction
from api_utils import (
    require_api_key, api_rate_limit, log_api_call, 
    handle_api_error, APIError, sanitize_input
)

# إنشاء Blueprint للـ API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# تطبيق CORS مع الإعدادات المحسّنة
# تعريف النطاقات المسموح بها بشكل مباشر
safe_origins = [
    'https://musabaqati.com',         # الموقع الرئيسي
    'https://www.musabaqati.com',     # البديل مع www
    'https://app.musabaqati.com',     # تطبيق الويب
    'https://admin.musabaqati.com',   # واجهة المشرفين
    'https://api.musabaqati.com'      # خادم API نفسه (للطلبات الداخلية)
]

# إضافة النطاقات المحلية في بيئة التطوير فقط
if app.debug:
    safe_origins.extend([
        'http://localhost:5000',
        'http://127.0.0.1:5000'
    ])

CORS(api_bp, 
     origins=safe_origins,
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'X-Admin-Verification'],
     supports_credentials=False,  # منع إرسال ملفات تعريف الارتباط عبر النطاقات
     max_age=3600                 # تخزين مؤقت للـ preflight لمدة ساعة
)

# معالج الأخطاء العامة
@api_bp.errorhandler(APIError)
def handle_api_exception(error):
    return handle_api_error(error)

# معالج خاص لطلبات OPTIONS (لدعم CORS preflight) لكل نقاط النهاية
@api_bp.route('/<path:path>', methods=['OPTIONS'])
@api_bp.route('/', methods=['OPTIONS'])
def handle_preflight_request(path=None):
    """
    معالج خاص لطلبات OPTIONS التي يرسلها المتصفح قبل الطلبات الحقيقية عبر النطاقات
    يسمح بالتحقق من الصلاحيات والرؤوس المسموح بها
    تحقق إضافي من الأصل (origin) للتأكد من أنه مدرج في القائمة المسموح بها
    """
    # تسجيل طلب preflight للتحليل
    origin = request.headers.get('Origin', '')
    path_info = path if path else "root"
    app.logger.debug(f"CORS Preflight request for path: {path_info} from origin: {origin}")
    
    # التحقق من الأصل المسموح به يدويًا كطبقة أمان إضافية
    if origin and origin not in safe_origins:
        app.logger.warning(f"CORS Preflight rejected for unauthorized origin: {origin}")
        return jsonify({
            'status': 'error',
            'error': 'Unauthorized origin'
        }), 403
    
    # تحضير الاستجابة مع رمز الحالة 204 - No Content
    response = make_response('', 204)
    
    # إضافة الرؤوس المطلوبة لـ CORS
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        # إضافة Vary: Origin لإخبار الوسطاء بتخزين الاستجابات بناءً على الأصل
        response.headers['Vary'] = 'Origin'
    
    # تحديد الطرق المسموح بها
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    
    # تحديد الرؤوس المسموح بها
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-Admin-Verification'
    
    # مدة صلاحية الاستجابة المسبقة (زيادة المدة لتقليل عدد طلبات preflight)
    response.headers['Access-Control-Max-Age'] = '86400'  # 24 ساعة
    
    # عدم السماح باستخدام بيانات الاعتماد
    response.headers['Access-Control-Allow-Credentials'] = 'false'
    
    return response

# نقطة نهاية صحة النظام
@api_bp.route('/health', methods=['GET'])
def health_check():
    """التحقق من صحة النظام وتوافر API"""
    return jsonify({
        'status': 'ok',
        'version': '1.0',
        'timestamp': int(time.time())
    })

# ============================================================
# نقاط نهاية معلومات المستخدم
# ============================================================

@api_bp.route('/user/info', methods=['GET'])
@require_api_key
@api_rate_limit("60 per minute")
def get_user_info():
    """الحصول على معلومات المستخدم الأساسية"""
    try:
        # استخدام معرف المستخدم المُخزن في validate_api_key
        user_id = g.user_id
        user = User.query.get(user_id)
        
        if not user:
            raise APIError("لم يتم العثور على المستخدم", status_code=404)
        
        # إنشاء كائن للاستجابة مع تجنب المعلومات الحساسة
        response = {
            'id': user.id,
            'username': user.username,
            'points': user.points,
            'referral_code': user.referral_code,
            'total_referrals': user.total_referrals,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
        
        # تسجيل الاستدعاء
        log_api_call('get_user_info', 200, user_id=user_id)
        
        return jsonify({
            'status': 'success',
            'data': response
        })
        
    except APIError as e:
        # سيتم التقاطها بواسطة معالج الأخطاء المحدد أعلاه
        raise
    except Exception as e:
        # تسجيل الخطأ وإرجاع رسالة خطأ عامة
        app.logger.error(f"خطأ في الحصول على معلومات المستخدم: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

@api_bp.route('/user/points', methods=['GET'])
@require_api_key
@api_rate_limit("60 per minute")
def get_user_points():
    """الحصول على رصيد نقاط المستخدم"""
    try:
        user_id = g.user_id
        user = User.query.get(user_id)
        
        if not user:
            raise APIError("لم يتم العثور على المستخدم", status_code=404)
        
        response = {
            'points': user.points,
            'timestamp': int(time.time())
        }
        
        # تسجيل الاستدعاء
        log_api_call('get_user_points', 200, user_id=user_id)
        
        return jsonify({
            'status': 'success',
            'data': response
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في الحصول على رصيد نقاط المستخدم: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

@api_bp.route('/user/transactions', methods=['GET'])
@require_api_key
@api_rate_limit("30 per minute")
def get_user_transactions():
    """الحصول على سجل المعاملات للمستخدم"""
    try:
        user_id = g.user_id
        
        # معالجة معلمات التصفية
        limit = min(int(request.args.get('limit', 10)), 50)  # الحد الأقصى 50
        offset = int(request.args.get('offset', 0))
        
        transactions = PointsTransaction.query.filter_by(
            user_id=user_id
        ).order_by(
            PointsTransaction.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        # تحويل النتائج إلى كائنات JSON
        result = []
        for tx in transactions:
            result.append({
                'id': tx.id,
                'amount': tx.amount,
                'balance_after': tx.balance_after,
                'transaction_type': tx.transaction_type,
                'description': tx.description,
                'created_at': tx.created_at.isoformat() if tx.created_at else None
            })
        
        # تسجيل الاستدعاء
        log_api_call('get_user_transactions', 200, user_id=user_id)
        
        return jsonify({
            'status': 'success',
            'data': result,
            'metadata': {
                'limit': limit,
                'offset': offset,
                'count': len(result)
            }
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في الحصول على سجل المعاملات: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

# ============================================================
# نقاط نهاية الإحالات
# ============================================================

@api_bp.route('/referrals', methods=['GET'])
@require_api_key
@api_rate_limit("30 per minute")
def get_user_referrals():
    """الحصول على قائمة المستخدمين الذين تمت إحالتهم"""
    try:
        user_id = g.user_id
        
        # معالجة معلمات التصفية
        limit = min(int(request.args.get('limit', 10)), 50)
        offset = int(request.args.get('offset', 0))
        
        # الحصول على سجلات الإحالة
        referrals = Referral.query.filter_by(
            referrer_id=user_id
        ).order_by(
            Referral.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        # تجميع المعلومات المطلوبة
        result = []
        for referral in referrals:
            referred_user = User.query.get(referral.referred_id)
            if referred_user:
                result.append({
                    'id': referral.id,
                    'referred_user': {
                        'id': referred_user.id,
                        'username': referred_user.username
                    },
                    'status': referral.status,
                    'reward_paid': referral.reward_paid,
                    'reward_amount': referral.reward_amount,
                    'created_at': referral.created_at.isoformat() if referral.created_at else None
                })
        
        # تسجيل الاستدعاء
        log_api_call('get_user_referrals', 200, user_id=user_id)
        
        return jsonify({
            'status': 'success',
            'data': result,
            'metadata': {
                'limit': limit,
                'offset': offset,
                'count': len(result),
                'total_referrals': User.query.get(user_id).total_referrals
            }
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في الحصول على قائمة الإحالات: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

# ============================================================
# نقاط نهاية المكافآت
# ============================================================

@api_bp.route('/rewards', methods=['GET'])
@require_api_key
@api_rate_limit("60 per minute")
def get_rewards():
    """الحصول على قائمة المكافآت المتاحة"""
    try:
        # معالجة معلمات التصفية
        limit = min(int(request.args.get('limit', 10)), 50)
        offset = int(request.args.get('offset', 0))
        
        # الحصول على المكافآت النشطة فقط
        rewards = Reward.query.filter_by(
            is_available=True
        ).order_by(
            Reward.points_required
        ).limit(limit).offset(offset).all()
        
        # تجميع المعلومات المطلوبة
        result = []
        for reward in rewards:
            result.append({
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'points_required': reward.points_required,
                'quantity': reward.quantity
            })
        
        # تسجيل الاستدعاء
        log_api_call('get_rewards', 200, user_id=getattr(g, 'user_id', None))
        
        return jsonify({
            'status': 'success',
            'data': result,
            'metadata': {
                'limit': limit,
                'offset': offset,
                'count': len(result)
            }
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في الحصول على قائمة المكافآت: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

# ============================================================
# نقاط نهاية API Keys
# ============================================================

@api_bp.route('/keys', methods=['GET'])
@require_api_key
@api_rate_limit("10 per minute")
def get_api_keys():
    """الحصول على قائمة مفاتيح API للمستخدم"""
    try:
        user_id = g.user_id
        
        # الحصول على المفاتيح (بدون إظهار المفتاح الكامل)
        keys = APIKey.query.filter_by(user_id=user_id).all()
        
        result = []
        for key in keys:
            # إخفاء المفتاح الكامل واستبداله بجزء فقط منه
            masked_key = f"{key.key[:8]}...{key.key[-4:]}" if key.key else None
            
            result.append({
                'id': key.id,
                'name': key.name,
                'key': masked_key,
                'permissions': key.permissions,
                'is_active': key.is_active,
                'usage_count': key.usage_count,
                'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                'created_at': key.created_at.isoformat() if key.created_at else None,
                'expires_at': key.expires_at.isoformat() if key.expires_at else None
            })
        
        # تسجيل الاستدعاء
        log_api_call('get_api_keys', 200, user_id=user_id)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في الحصول على قائمة مفاتيح API: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

@api_bp.route('/keys', methods=['POST'])
@require_api_key
@api_rate_limit("5 per hour")
def create_api_key():
    """إنشاء مفتاح API جديد"""
    try:
        user_id = g.user_id
        
        # قراءة بيانات الطلب
        data = request.get_json()
        if not data:
            raise APIError("البيانات المطلوبة غير موجودة", status_code=400)
        
        # تنظيف وتحقق من البيانات المدخلة
        cleaned_data = sanitize_input(data, 
                                     allowed_fields=['name', 'permissions', 'expires_days'],
                                     max_length=100)
        
        name = cleaned_data.get('name')
        permissions = cleaned_data.get('permissions', 'read')
        expires_days = int(cleaned_data.get('expires_days', 0)) if cleaned_data.get('expires_days') else None
        
        # التحقق من صحة البيانات المُدخلة
        valid_permissions = ['read', 'write', 'admin']
        if permissions not in valid_permissions:
            raise APIError(f"الصلاحيات غير صالحة. يجب أن تكون واحدة من: {', '.join(valid_permissions)}", status_code=400)
        
        if expires_days is not None and expires_days < 0:
            raise APIError("عدد أيام انتهاء الصلاحية يجب أن يكون عددًا موجبًا", status_code=400)
        
        # إنشاء المفتاح
        api_key = APIKey.generate_key(
            user_id=user_id,
            name=name,
            permissions=permissions,
            expires_days=expires_days
        )
        
        if not api_key:
            raise APIError("فشل إنشاء المفتاح", status_code=500)
        
        # تسجيل الاستدعاء
        log_api_call('create_api_key', 201, user_id=user_id)
        
        # إرجاع المفتاح الكامل - فقط مرة واحدة عند الإنشاء
        return jsonify({
            'status': 'success',
            'data': {
                'id': api_key.id,
                'key': api_key.key,  # المفتاح الكامل - سيتم عرضه مرة واحدة فقط
                'name': api_key.name,
                'permissions': api_key.permissions,
                'is_active': api_key.is_active,
                'created_at': api_key.created_at.isoformat() if api_key.created_at else None,
                'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None
            },
            'message': 'تم إنشاء المفتاح بنجاح. يرجى الاحتفاظ بالمفتاح الكامل، لن يتم عرضه مرة أخرى.'
        }), 201
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في إنشاء مفتاح API: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

@api_bp.route('/keys/<int:key_id>', methods=['DELETE'])
@require_api_key
@api_rate_limit("10 per hour")
def delete_api_key(key_id):
    """إلغاء تنشيط مفتاح API"""
    try:
        user_id = g.user_id
        
        # البحث عن المفتاح والتأكد من ملكية المستخدم له
        api_key = APIKey.query.filter_by(id=key_id, user_id=user_id).first()
        
        if not api_key:
            raise APIError("لم يتم العثور على المفتاح", status_code=404)
        
        # إلغاء تنشيط المفتاح (عدم حذفه فعليًا للحفاظ على سجل الاستخدام)
        api_key.is_active = False
        db.session.commit()
        
        # تسجيل الاستدعاء
        log_api_call('delete_api_key', 200, user_id=user_id, details={'key_id': key_id})
        
        return jsonify({
            'status': 'success',
            'message': 'تم إلغاء تنشيط المفتاح بنجاح'
        })
        
    except APIError as e:
        raise
    except Exception as e:
        app.logger.error(f"خطأ في إلغاء تنشيط مفتاح API: {str(e)}")
        raise APIError("حدث خطأ أثناء معالجة الطلب", status_code=500)

# تسجيل Blueprint في التطبيق
app.register_blueprint(api_bp)

# إضافة نقطة نهاية للتوثيق
@app.route('/api/docs')
def api_docs():
    """توثيق واجهة برمجة التطبيقات"""
    return jsonify({
        'name': 'مسابقاتي API',
        'version': 'v1',
        'base_url': '/api/v1',
        'endpoints': [
            {'path': '/health', 'method': 'GET', 'description': 'التحقق من صحة النظام'},
            {'path': '/user/info', 'method': 'GET', 'description': 'الحصول على معلومات المستخدم'},
            {'path': '/user/points', 'method': 'GET', 'description': 'الحصول على رصيد نقاط المستخدم'},
            {'path': '/user/transactions', 'method': 'GET', 'description': 'الحصول على سجل المعاملات'},
            {'path': '/referrals', 'method': 'GET', 'description': 'الحصول على قائمة الإحالات'},
            {'path': '/rewards', 'method': 'GET', 'description': 'الحصول على قائمة المكافآت'},
            {'path': '/keys', 'method': 'GET', 'description': 'الحصول على قائمة مفاتيح API'},
            {'path': '/keys', 'method': 'POST', 'description': 'إنشاء مفتاح API جديد'},
            {'path': '/keys/<key_id>', 'method': 'DELETE', 'description': 'إلغاء تنشيط مفتاح API'}
        ],
        'authentication': 'Bearer Token',
        'rate_limiting': 'نعم - مختلف لكل نقطة نهاية'
    })