"""
وحدة أمان وحماية نظام الإحالة
تحتوي على وظائف للتحقق من صحة الإحالات ومراقبة النشاط المشبوه
"""
from app import app, db
from models import User, Referral, ReferralIPLog, AdminNotification
from datetime import datetime, timedelta
from sqlalchemy import func
import config

def track_referral_ip(ip_address):
    """
    تسجيل وتتبع عنوان IP المستخدم للإحالة
    التحقق من تجاوز الحد المسموح من الإحالات من نفس العنوان
    
    عودة:
    - (True, None) إذا كان العنوان آمن ويمكن استخدامه
    - (False, سبب_المنع) إذا كان هناك سبب لمنع الإحالة
    """
    now = datetime.utcnow()
    time_24h_ago = now - timedelta(hours=24)
    
    # البحث عن سجل هذا الـ IP
    ip_log = ReferralIPLog.query.filter_by(ip_address=ip_address).first()
    
    if ip_log:
        # تحقق إذا كان الـ IP محظورًا مسبقًا
        if ip_log.is_blocked:
            return False, "ip_blocked"
        
        # تحقق من عدد الإحالات من هذا الـ IP خلال آخر 24 ساعة
        recent_referrals = Referral.query.filter(
            Referral.ip_address == ip_address,
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
                    message=f"تم حظر عنوان IP {ip_address} تلقائيًا بسبب تجاوزه الحد المسموح من الإحالات في 24 ساعة ({recent_referrals} إحالات).",
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
            ip_address=ip_address,
            referral_count=1,
            first_seen=now,
            last_seen=now
        )
        db.session.add(ip_log)
        db.session.commit()
    
    return True, None


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


def verify_referral(referral_id, verification_method=None):
    """
    التحقق من صحة إحالة والموافقة عليها
    يمكن أن تكون بسبب تفعيل البريد أو المشاركة في مسابقة
    
    عودة:
    - True إذا تم التحقق بنجاح
    - False إذا فشل التحقق
    """
    referral = Referral.query.get(referral_id)
    if not referral:
        return False
    
    # تعيين الإحالة كتم التحقق منها
    referral.is_verified = True
    referral.verified_at = datetime.utcnow()
    referral.verification_method = verification_method
    referral.status = "verified"
    
    if verification_method:
        referral.verification_method = verification_method
    
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
                
                # إضافة مكافأة الإحالة الأساسية
                referrer.add_points(reward_amount)
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
                            referrer.add_points(bonus)
                            referrer.monthly_referral_points += bonus
                            referrer.total_referral_points += bonus
                            
                            # إنشاء إشعار للمستخدم بالوصول للمعلم
                            app.logger.info(f"User {referrer.username} reached referral milestone: {milestone} referrals, bonus: {bonus} points")
                
                # منح المستخدم الجديد المكافأة الترحيبية
                if config.REFERRAL_WELCOME_BONUS > 0:
                    referred.add_points(config.REFERRAL_WELCOME_BONUS)
                    app.logger.info(f"New user {referred.username} received welcome bonus: {config.REFERRAL_WELCOME_BONUS} points")
            
            else:
                # تسجيل سبب عدم دفع المكافأة
                referral.rejection_reason = f"تم تجاوز {reason}"
                app.logger.warning(f"Referral reward not paid to {referrer.username}, reason: {reason}")
    
    db.session.commit()
    return True


def reject_referral(referral_id, reason):
    """
    رفض إحالة وتسجيل سبب الرفض
    """
    referral = Referral.query.get(referral_id)
    if not referral:
        return False
    
    referral.status = "rejected"
    referral.rejection_reason = reason
    
    # إذا كانت المكافأة قد دُفعت، استرجاعها
    if referral.reward_paid and referral.reward_amount > 0:
        referrer = User.query.get(referral.referrer_id)
        if referrer and referrer.points >= referral.reward_amount:
            referrer.points -= referral.reward_amount
            referrer.monthly_referral_points -= referral.reward_amount
            referrer.total_referral_points -= referral.reward_amount
            referrer.total_referrals -= 1
            
            referral.reward_paid = False
    
    db.session.commit()
    return True


def check_pending_verifications():
    """
    فحص الإحالات المعلقة والتحقق من استيفائها للشروط
    يتم استدعاؤها دوريًا أو عند تسجيل دخول المستخدم
    """
    now = datetime.utcnow()
    verification_deadline = now - timedelta(days=config.REFERRAL_VERIFICATION_DAYS)
    
    # الحصول على الإحالات المعلقة
    pending_referrals = Referral.query.filter(
        Referral.status == "pending",
        Referral.is_verified == False,
        Referral.created_at < verification_deadline
    ).all()
    
    for referral in pending_referrals:
        # التحقق مما إذا كان المستخدم المُحال قد شارك في مسابقة
        if config.REFERRAL_REQUIRE_COMPETITION_PARTICIPATION:
            referred_user = User.query.get(referral.referred_id)
            has_participated = referred_user.participations.count() > 0
            
            if has_participated:
                # التحقق من الإحالة بناءً على المشاركة في المسابقة
                verify_referral(referral.id, "competition_participation")
            else:
                # تجاوزت المدة المسموحة دون مشاركة في مسابقة
                reject_referral(referral.id, "لم يتم المشاركة في أي مسابقة خلال المدة المحددة")
    
    db.session.commit()
    return len(pending_referrals)