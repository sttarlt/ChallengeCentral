"""
وحدة أمان وحماية نظام الإحالة
تحتوي على وظائف للتحقق من صحة الإحالات ومراقبة النشاط المشبوه
"""
from app import app, db
from models import User, Referral, ReferralIPLog, AdminNotification
from datetime import datetime, timedelta
from sqlalchemy import func
import config

def get_client_ip(request):
    """
    الحصول على عنوان IP الحقيقي للعميل بشكل آمن
    مع مراعاة الوسطاء والشبكات العكسية
    
    Args:
        request: كائن Flask Request
    
    عودة:
        العنوان IP الحقيقي للمستخدم
    """
    if request and 'X-Forwarded-For' in request.headers:
        # تقسيم سلسلة العناوين واختيار أول عنصر (عنوان العميل الأصلي)
        x_forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if x_forwarded_for:
            # التحقق من صحة تنسيق IP (يجب إضافة تحقق أكثر تفصيلاً)
            if len(x_forwarded_for) <= 45:  # الحد الأقصى لطول IPv6
                return x_forwarded_for
    
    # إذا لم يكن هناك X-Forwarded-For، استخدم remote_addr
    return request.remote_addr if request else None


def track_referral_ip(ip_address, request=None):
    """
    تسجيل وتتبع عنوان IP المستخدم للإحالة
    التحقق من تجاوز الحد المسموح من الإحالات من نفس العنوان
    
    Args:
        ip_address: عنوان IP للتحقق منه
        request: كائن Flask Request (اختياري)
    
    عودة:
        (True, None) إذا كان العنوان آمن ويمكن استخدامه
        (False, سبب_المنع) إذا كان هناك سبب لمنع الإحالة
    """
    try:
        # الحصول على عنوان IP الحقيقي إذا تم تمرير كائن request
        real_ip = get_client_ip(request) if request else ip_address
        
        if not real_ip:
            app.logger.warning("Failed to determine client IP address")
            return False, "invalid_ip"
        
        now = datetime.utcnow()
        time_24h_ago = now - timedelta(hours=24)
        
        # البحث عن سجل هذا الـ IP
        ip_log = ReferralIPLog.query.filter_by(ip_address=real_ip).first()
        
        if ip_log:
            # تحقق إذا كان الـ IP محظورًا مسبقًا
            if ip_log.is_blocked:
                return False, "ip_blocked"
            
            # تحقق من عدد الإحالات من هذا الـ IP خلال آخر 24 ساعة
            recent_referrals = Referral.query.filter(
                Referral.ip_address == real_ip,
                Referral.created_at >= time_24h_ago
            ).count()
            
            # إذا تجاوز الحد المسموح
            if recent_referrals >= config.REFERRAL_MAX_PER_IP_24H:
                # حظر الـ IP إذا وصل لضعف الحد المسموح
                if recent_referrals >= config.REFERRAL_MAX_PER_IP_24H * 2:
                    ip_log.is_blocked = True
                    # إنشاء إشعار للمسؤول
                    notification = AdminNotification(
                        title="تم حظر عنوان IP بسبب الإحالات المتكررة",
                        message=f"تم حظر عنوان IP {real_ip} تلقائيًا بسبب تجاوزه الحد المسموح من الإحالات في 24 ساعة ({recent_referrals} إحالات).",
                        notification_type="ip_blocked"
                    )
                    db.session.add(notification)
                    
                db.session.commit()
                return False, "max_referrals_per_ip"
            
            # تحديث السجل
            ip_log.referral_count += 1
            ip_log.last_seen = now
            db.session.commit()
        else:
            # إنشاء سجل جديد لهذا الـ IP
            ip_log = ReferralIPLog(
                ip_address=real_ip,
                referral_count=1,
                first_seen=now,
                last_seen=now
            )
            db.session.add(ip_log)
            db.session.commit()
        
        return True, None
    except Exception as e:
        app.logger.error(f"خطأ في تتبع عنوان IP: {str(e)}")
        db.session.rollback()
        return False, "error"


def detect_suspicious_activity(user_id):
    """
    كشف النشاط المشبوه في الإحالات
    التحقق من معدل الإحالات غير الطبيعي
    
    عودة:
    - (False, None) إذا لم يتم العثور على نشاط مشبوه
    - (True, نوع_النشاط) إذا تم الكشف عن نشاط مشبوه
    """
    now = datetime.utcnow()
    time_1h_ago = now - timedelta(hours=1)
    
    # عدد الإحالات في الساعة الأخيرة
    recent_referrals = Referral.query.filter(
        Referral.referrer_id == user_id,
        Referral.created_at >= time_1h_ago
    ).count()
    
    # تحقق من تجاوز المعدل المشبوه
    if recent_referrals >= config.REFERRAL_SUSPICIOUS_RATE:
        # إنشاء إشعار للمسؤول
        notification = AdminNotification(
            title="نشاط إحالة مشبوه",
            message=f"تم اكتشاف معدل إحالات غير طبيعي للمستخدم ID: {user_id}. {recent_referrals} إحالات في الساعة الأخيرة.",
            notification_type="suspicious_rate",
            related_user_id=user_id
        )
        db.session.add(notification)
        db.session.commit()
        
        # وضع علامة على الإحالات الأخيرة كمشبوهة
        suspicious_referrals = Referral.query.filter(
            Referral.referrer_id == user_id,
            Referral.created_at >= time_1h_ago
        ).all()
        
        for referral in suspicious_referrals:
            referral.is_suspicious = True
        
        db.session.commit()
        return True, "high_rate"
    
    return False, None


def verify_referral(referral_id, verification_method=None, request=None):
    """
    التحقق من صحة إحالة والموافقة عليها
    يمكن أن تكون بسبب تفعيل البريد أو المشاركة في مسابقة
    
    Args:
        referral_id: معرّف الإحالة
        verification_method: طريقة التحقق (مثلاً: admin_verification, competition_participation)
        request: كائن Flask Request للحصول على معلومات IP والمتصفح
    
    عودة:
        - True إذا تم التحقق بنجاح
        - False إذا فشل التحقق
    """
    try:
        referral = Referral.query.get(referral_id)
        if not referral:
            app.logger.warning(f"لم يتم العثور على الإحالة {referral_id}")
            return False
        
        # التحقق من عدم معالجة الإحالة مسبقاً
        if referral.status != "pending" or referral.is_verified:
            app.logger.warning(f"محاولة التحقق من إحالة تمت معالجتها بالفعل {referral_id}")
            return False
        
        # بدء transaction لضمان تنفيذ جميع العمليات كوحدة واحدة
        db.session.begin_nested()
        
        # تعيين الإحالة كتم التحقق منها
        referral.is_verified = True
        referral.verified_at = datetime.utcnow()
        referral.verification_method = verification_method
        referral.status = "verified"
        
        # إذا لم يتم دفع المكافأة بعد، ادفعها الآن
        if not referral.reward_paid:
            # الحصول على المرجع والمستخدم المُحال
            referrer = User.query.get(referral.referrer_id)
            referred = User.query.get(referral.referred_id)
            
            if referrer and referred:
                # منح مكافأة المرجع
                reward_amount = config.REFERRAL_REWARD_PER_FRIEND
                
                # التحقق من إمكانية تلقي المكافأة (حسب الحدود)
                can_add, reason = referrer.can_receive_referral_reward(reward_amount)
                
                if can_add:
                    # زيادة عدد الإحالات الناجحة
                    referrer.total_referrals += 1
                    
                    # إضافة مكافأة الإحالة الأساسية باستخدام نظام التسجيل المحسّن
                    add_success = referrer.add_points(
                        points=reward_amount,
                        transaction_type='referral_reward',
                        related_id=referral_id,
                        description=f'مكافأة إحالة المستخدم {referred.username}',
                        request=request
                    )
                    
                    if add_success:
                        # تحديث عدادات الإحالة
                        referrer.monthly_referral_points += reward_amount
                        referrer.total_referral_points += reward_amount
                        
                        # تسجيل قيمة المكافأة المدفوعة
                        referral.reward_amount = reward_amount
                        referral.reward_paid = True
                        
                        # التحقق من وصول المستخدم إلى معلم (5 أو 10 إحالات) لمكافآت إضافية
                        for milestone, bonus in config.REFERRAL_MILESTONE_REWARDS.items():
                            if referrer.total_referrals == milestone:
                                # التحقق مرة أخرى من إمكانية تلقي المكافأة الإضافية
                                can_add_bonus, _ = referrer.can_receive_referral_reward(bonus)
                                if can_add_bonus:
                                    # إضافة مكافأة المرحلة باستخدام نظام التسجيل المحسّن
                                    milestone_success = referrer.add_points(
                                        points=bonus,
                                        transaction_type='milestone_reward',
                                        related_id=referral_id,
                                        description=f'مكافأة إضافية - {milestone} إحالات',
                                        request=request
                                    )
                                    
                                    if milestone_success:
                                        # تحديث عدادات الإحالة
                                        referrer.monthly_referral_points += bonus
                                        referrer.total_referral_points += bonus
                                        
                                        # إنشاء إشعار للمستخدم بالوصول للمعلم
                                        app.logger.info(f"وصل المستخدم {referrer.username} لمعلم إحالة: {milestone} إحالات، مكافأة: {bonus} نقطة")
                        
                        # منح المستخدم الجديد المكافأة الترحيبية
                        if config.REFERRAL_WELCOME_BONUS > 0:
                            # استخدام نظام التسجيل المحسّن للمستخدم الجديد
                            welcome_success = referred.add_points(
                                points=config.REFERRAL_WELCOME_BONUS,
                                transaction_type='welcome_bonus',
                                related_id=referral_id,
                                description='مكافأة ترحيبية للتسجيل عبر دعوة صديق',
                                request=request
                            )
                            
                            if welcome_success:
                                app.logger.info(f"حصل المستخدم الجديد {referred.username} على مكافأة ترحيبية: {config.REFERRAL_WELCOME_BONUS} نقطة")
                            else:
                                app.logger.error(f"فشل في إضافة المكافأة الترحيبية للمستخدم {referred.username}")
                    else:
                        db.session.rollback()
                        app.logger.error(f"فشل في إضافة مكافأة الإحالة للمستخدم {referrer.username}")
                        return False
                
                else:
                    # تسجيل سبب عدم دفع المكافأة
                    referral.rejection_reason = f"تم تجاوز {reason}"
                    app.logger.warning(f"لم يتم دفع مكافأة الإحالة للمستخدم {referrer.username}، السبب: {reason}")
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ عام في التحقق من الإحالة: {str(e)}")
        return False


def reject_referral(referral_id, reason, request=None):
    """
    رفض إحالة وتسجيل سبب الرفض
    
    Args:
        referral_id: معرّف الإحالة
        reason: سبب الرفض
        request: كائن Flask Request للحصول على معلومات IP والمتصفح
    
    عودة:
        - True إذا تم الرفض بنجاح
        - False إذا فشلت العملية
    """
    try:
        referral = Referral.query.get(referral_id)
        if not referral:
            app.logger.warning(f"لم يتم العثور على الإحالة {referral_id}")
            return False
        
        # بدء transaction لضمان تنفيذ جميع العمليات كوحدة واحدة
        db.session.begin_nested()
        
        referral.status = "rejected"
        referral.rejection_reason = reason
        
        # إذا كانت المكافأة قد دُفعت، استرجاعها
        if referral.reward_paid and referral.reward_amount > 0:
            referrer = User.query.get(referral.referrer_id)
            if referrer and referrer.points >= referral.reward_amount:
                # تسجيل عملية استرجاع النقاط في سجل المعاملات
                reclaim_success = referrer.use_points(
                    points=referral.reward_amount,
                    transaction_type='referral_rejection',
                    related_id=referral_id,
                    description=f'استرجاع مكافأة إحالة - السبب: {reason}',
                    request=request
                )
                
                if reclaim_success:
                    # تحديث عدادات الإحالة
                    referrer.monthly_referral_points -= referral.reward_amount
                    referrer.total_referral_points -= referral.reward_amount
                    referrer.total_referrals -= 1
                    
                    referral.reward_paid = False
                    
                    app.logger.info(f"تم رفض الإحالة {referral_id} واسترجاع {referral.reward_amount} نقطة من المستخدم {referrer.username}")
                else:
                    db.session.rollback()
                    app.logger.error(f"فشل في استرجاع النقاط من المستخدم {referrer.username}")
                    return False
        
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ عام في رفض الإحالة: {str(e)}")
        return False


def check_pending_verifications():
    """
    فحص الإحالات المعلقة والتحقق من استيفائها للشروط
    يتم استدعاؤها دوريًا أو عند تسجيل دخول المستخدم
    
    عودة:
        عدد الإحالات المعلقة التي تمت معالجتها
    """
    processed_count = 0
    
    try:
        now = datetime.utcnow()
        verification_deadline = now - timedelta(days=config.REFERRAL_VERIFICATION_DAYS)
        
        # الحصول على الإحالات المعلقة
        pending_referrals = Referral.query.filter(
            Referral.status == "pending",
            Referral.is_verified == False,
            Referral.created_at < verification_deadline
        ).all()
        
        if not pending_referrals:
            return 0
            
        app.logger.info(f"بدء التحقق من {len(pending_referrals)} إحالات معلقة...")
        
        for referral in pending_referrals:
            try:
                # التحقق مما إذا كان المستخدم المُحال قد شارك في مسابقة
                if config.REFERRAL_REQUIRE_COMPETITION_PARTICIPATION:
                    referred_user = User.query.get(referral.referred_id)
                    
                    if not referred_user:
                        app.logger.warning(f"المستخدم المُحال برقم {referral.referred_id} غير موجود، رفض الإحالة")
                        reject_referral(referral.id, "المستخدم غير موجود")
                        processed_count += 1
                        continue
                        
                    has_participated = referred_user.participations.count() > 0
                    
                    if has_participated:
                        # التحقق من الإحالة بناءً على المشاركة في المسابقة
                        if verify_referral(referral.id, "competition_participation"):
                            app.logger.info(f"تم التحقق من الإحالة {referral.id} للمستخدم {referred_user.username}")
                            processed_count += 1
                    else:
                        # تجاوزت المدة المسموحة دون مشاركة في مسابقة
                        if reject_referral(referral.id, "لم يتم المشاركة في أي مسابقة خلال المدة المحددة"):
                            app.logger.info(f"تم رفض الإحالة {referral.id} للمستخدم {referred_user.username} لعدم المشاركة في المسابقات")
                            processed_count += 1
            except Exception as e:
                app.logger.error(f"خطأ في معالجة الإحالة {referral.id}: {str(e)}")
                db.session.rollback()
        
        db.session.commit()
        app.logger.info(f"تمت معالجة {processed_count} من أصل {len(pending_referrals)} إحالات معلقة")
        return processed_count
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"خطأ عام في التحقق من الإحالات المعلقة: {str(e)}")
        return processed_count


def is_valid_session(user_id, action_type=None):
    """
    التحقق من صحة جلسة المستخدم وأهليته لتنفيذ عمليات على النقاط
    هذه الدالة تساعد في حماية عمليات النقاط (كربتو)
    
    Args:
        user_id: معرّف المستخدم المطلوب التحقق منه
        action_type: نوع العملية (إضافة نقاط، سحب نقاط، إلخ) للتسجيل المتكامل
    
    عودة:
        - True إذا كانت الجلسة صالحة والمستخدم مؤهل
        - False إذا كانت هناك مشكلة في الجلسة أو المستخدم
    """
    from flask_login import current_user
    
    # التحقق من أن المستخدم مسجل دخوله
    if not current_user.is_authenticated:
        app.logger.warning(f"محاولة تعديل رصيد المستخدم {user_id} بدون تسجيل دخول! نوع العملية: {action_type}")
        
        # إنشاء إشعار للمشرف للتحقيق في هذه المحاولة
        notification = AdminNotification(
            title="محاولة مشبوهة لتعديل الرصيد",
            message=f"تم رصد محاولة لتعديل رصيد المستخدم رقم {user_id} بدون تسجيل دخول. نوع العملية: {action_type}",
            notification_type="security_alert"
        )
        db.session.add(notification)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            
        return False
    
    # التحقق من أن المستخدم المطلوب هو نفسه المسجل الدخول أو مشرف
    if current_user.id != user_id and not current_user.is_admin:
        app.logger.warning(f"محاولة المستخدم {current_user.id} تعديل رصيد المستخدم {user_id} بدون صلاحيات! نوع العملية: {action_type}")
        
        # إنشاء إشعار للمشرف حول محاولة التعديل غير المصرح بها
        notification = AdminNotification(
            title="محاولة غير مصرح بها لتعديل الرصيد",
            message=f"حاول المستخدم {current_user.username} (ID: {current_user.id}) تعديل رصيد المستخدم رقم {user_id} بدون صلاحيات. نوع العملية: {action_type}",
            notification_type="security_alert",
            related_user_id=current_user.id
        )
        db.session.add(notification)
        try:
            db.session.commit()
        except:
            db.session.rollback()
            
        return False
    
    # سجل العملية المسموح بها للتحليل الأمني
    if action_type and current_user.is_admin and current_user.id != user_id:
        app.logger.info(f"المشرف {current_user.username} (ID: {current_user.id}) يقوم بتعديل رصيد المستخدم {user_id}. نوع العملية: {action_type}")
    
    return True