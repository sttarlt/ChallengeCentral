from flask import render_template, redirect, url_for, flash, request, abort, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import desc, func, or_
from functools import wraps
from app import app, db, limiter
from models import User, Competition, Reward, Participation, RewardRedemption, ChatRoom, ChatRoomMember, Message, PointsPackage, Referral, ReferralIPLog, AdminNotification, APIKey, Question, PointsTransaction
import config
import referral_security
from audit_log import log_audit_event, monitor_login_attempts, log_sensitive_action, EVENT_TYPES, SEVERITY_LEVELS
from forms import (
    LoginForm, RegistrationForm, CompetitionForm, RewardForm,
    ParticipationForm, RedeemRewardForm, RedemptionStatusForm,
    CreateChatRoomForm, SendMessageForm, DirectMessageForm,
    PointsPackageForm, AdminPointsForm, QuestionForm
)
from datetime import datetime

# مساعد للتحقق من كون المستخدم مشرف
def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            app.logger.debug(f"Admin access denied: User not authenticated")
            app.logger.warning(f"Unauthenticated user attempted to access admin endpoint: {request.path}")
            flash('يرجى تسجيل الدخول كمشرف للوصول إلى لوحة التحكم', 'warning')
            return redirect(url_for('admin_login'))
        if not current_user.is_admin:
            app.logger.debug(f"Admin access denied: User {current_user.username} is not admin")
            app.logger.warning(f"Non-admin user {current_user.username} attempted to access admin endpoint: {request.path}")
            flash('حسابك ليس لديه صلاحيات المشرف اللازمة للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return decorated_view


@app.route('/health')
def health_check():
    """Simple health check endpoint to verify the app is responding"""
    return jsonify({"status": "ok", "message": "Flask application is running"}), 200

@app.route('/')
def index():
    try:
        active_competitions = Competition.query.filter(
            Competition.is_active == True,
            Competition.end_date >= datetime.utcnow()
        ).order_by(Competition.start_date).limit(4).all()
        
        popular_rewards = Reward.query.filter_by(is_available=True).order_by(
            Reward.points_required
        ).limit(4).all()
        
        top_users = User.query.order_by(User.points.desc()).limit(5).all()
    except Exception as e:
        app.logger.error(f"Error loading index page: {str(e)}")
        # Return a simplified version if database queries fail
        active_competitions = []
        popular_rewards = []
        top_users = []
    
    return render_template(
        'index.html',
        competitions=active_competitions,
        rewards=popular_rewards,
        top_users=top_users
    )


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute, 100 per hour")  # حماية معدل الطلبات
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        success = False
        
        # الحصول على عنوان IP
        ip_address = request.remote_addr
        if 'X-Forwarded-For' in request.headers:
            ip_address = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('تم تسجيل الدخول بنجاح', 'success')
            success = True
            
            # تسجيل محاولة تسجيل الدخول الناجحة
            details = f"تسجيل دخول ناجح من المتصفح {request.user_agent.browser}"
            monitor_login_attempts(user.username, True, ip_address, details)
            
            return redirect(next_page or url_for('dashboard'))
        else:
            # تسجيل محاولة تسجيل الدخول الفاشلة
            email = form.email.data
            username = user.username if user else email  # استخدم البريد الإلكتروني إذا لم يتم العثور على المستخدم
            details = f"محاولة فاشلة لتسجيل الدخول باستخدام البريد الإلكتروني: {email}"
            monitor_login_attempts(username, False, ip_address, details)
            
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute, 20 per hour")  # حماية معدل الطلبات
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # التقاط كود الإحالة من جلسة المستخدم (إذا كان قد زار رابط إحالة قبل ذلك)
    referral_code = session.get('referral_code', None)
    referrer = None
    
    # استرجاع معلومات الإحالة المخزنة في الجلسة
    referral_ip = session.get('referral_ip', None)
    referral_user_agent = session.get('referral_user_agent', None)
    referral_suspicious = session.get('referral_suspicious', False)
    
    if referral_code:
        # البحث عن المستخدم صاحب كود الإحالة
        referrer = User.query.filter_by(referral_code=referral_code).first()
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        
        # توليد كود إحالة للمستخدم الجديد
        user.generate_referral_code()
        
        db.session.add(user)
        db.session.commit()
        
        # منح المكافأة الترحيبية للمستخدم الجديد من حساب المشرف المركزي
        welcome_bonus = config.REFERRAL_WELCOME_BONUS
        if welcome_bonus > 0:
            # الحصول على المشرف المركزي
            admin = User.query.filter_by(is_admin=True).first()
            
            if admin and admin.points >= welcome_bonus:
                # إضافة النقاط من حساب المشرف المركزي
                success = user.add_points(
                    points=welcome_bonus,
                    transaction_type='welcome_bonus',
                    description=f'مكافأة ترحيبية للمستخدم الجديد - {welcome_bonus} كربتو',
                    created_by_id=admin.id,
                    request=request,
                    from_admin=True
                )
                if success:
                    flash(f'تهانينا! لقد حصلت على {welcome_bonus} كربتو كمكافأة ترحيبية', 'success')
            else:
                # في حالة عدم وجود حساب مشرف أو عدم وجود نقاط كافية، نسجل هذا في السجلات
                app.logger.warning(f"لم تتم إضافة المكافأة الترحيبية ({welcome_bonus} كربتو) للمستخدم {user.username} - لا توجد نقاط كافية في حساب المشرف")
        
        # إذا كان المستخدم قد سجل عبر رابط إحالة، نقوم بربطه بالمستخدم الذي قام بالإحالة
        if referrer:
            # إضافة علاقة الإحالة
            user.referred_by_id = referrer.id
            
            # إنشاء سجل إحالة جديد مع معلومات تتبع كاملة
            referral = Referral(
                referrer_id=referrer.id,
                referred_id=user.id,
                status='pending',  # تعليق حالة الإحالة حتى يتم التحقق
                ip_address=referral_ip,
                user_agent=referral_user_agent,
                is_suspicious=referral_suspicious
            )
            
            db.session.add(referral)
            db.session.commit()
            
            # التحقق مما إذا كان يجب التحقق من الإحالة عبر المشاركة في مسابقة
            if config.REFERRAL_REQUIRE_COMPETITION_PARTICIPATION:
                # لا تتم إضافة النقاط للمُحيل حتى يتم التحقق
                flash('لتفعيل مكافأة الإحالة، يجب عليك المشاركة في مسابقة واحدة على الأقل خلال الأيام القادمة', 'info')
            else:
                # إذا لم يكن التحقق مطلوبًا، نقوم بتفعيل الإحالة فوراً
                referral_security.verify_referral(referral.id, "direct_registration")
                
            # مسح معلومات الإحالة من الجلسة
            for key in ['referral_code', 'referral_ip', 'referral_user_agent', 'referral_suspicious']:
                if key in session:
                    session.pop(key, None)
            
        db.session.commit()
        flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form, referrer=referrer)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))


@app.route('/api-keys', methods=['GET'])
@login_required
def api_keys():
    """إدارة مفاتيح API للمستخدم"""
    # الحصول على المفاتيح النشطة للمستخدم الحالي
    active_keys = APIKey.query.filter_by(
        user_id=current_user.id
    ).order_by(APIKey.created_at.desc()).all()
    
    # الحصول على الحد الأقصى لعدد المفاتيح من الإعدادات
    max_keys = getattr(config, 'API_MAX_KEYS_PER_USER', 5)
    
    # التحقق من وجود مفتاح جديد في الجلسة (إذا تم إنشاؤه للتو)
    new_key = None
    if 'new_api_key_id' in session:
        new_key = APIKey.query.get(session.pop('new_api_key_id'))
    
    return render_template(
        'api_keys.html',
        api_keys=active_keys,
        max_keys_per_user=max_keys,
        new_key=new_key
    )


@app.route('/api-keys/create', methods=['POST'])
@login_required
@limiter.limit("5 per hour")
def create_api_key():
    """إنشاء مفتاح API جديد"""
    # التحقق من عدد المفاتيح الحالية
    current_keys_count = APIKey.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).count()
    
    max_keys = getattr(config, 'API_MAX_KEYS_PER_USER', 5)
    
    if current_keys_count >= max_keys:
        flash('لقد وصلت للحد الأقصى من مفاتيح API المسموح بها', 'warning')
        return redirect(url_for('api_keys'))
    
    # الحصول على البيانات من النموذج
    key_name = request.form.get('key_name')
    permissions = request.form.get('permissions', 'read')
    expires_days_str = request.form.get('expires_days')
    
    # تحويل مدة الصلاحية إلى عدد صحيح
    expires_days = None
    if expires_days_str:
        try:
            expires_days = int(expires_days_str)
        except ValueError:
            pass
    
    # التحقق من الصلاحيات (فقط المشرفين يمكنهم إنشاء مفاتيح بصلاحيات المشرف)
    if permissions == 'admin' and not current_user.is_admin:
        permissions = 'read'
    
    # إنشاء المفتاح الجديد
    new_key = APIKey.generate_key(
        user_id=current_user.id,
        name=key_name,
        permissions=permissions,
        expires_days=expires_days
    )
    
    if new_key:
        # تخزين معرف المفتاح الجديد في الجلسة لعرضه مرة واحدة
        session['new_api_key_id'] = new_key.id
        flash('تم إنشاء مفتاح API جديد بنجاح', 'success')
        
        # تسجيل الحدث
        log_audit_event(
            event_type=EVENT_TYPES['SECURITY'],
            severity=SEVERITY_LEVELS['INFO'],
            details=f"إنشاء مفتاح API جديد بصلاحيات: {permissions}",
            user_id=current_user.id,
            username=current_user.username,
            ip_address=request.remote_addr
        )
    else:
        flash('حدث خطأ أثناء إنشاء المفتاح', 'danger')
    
    return redirect(url_for('api_keys'))


@app.route('/api-keys/<int:key_id>/deactivate', methods=['POST'])
@login_required
def deactivate_api_key(key_id):
    """إلغاء تنشيط مفتاح API"""
    # البحث عن المفتاح والتأكد من ملكية المستخدم له
    api_key = APIKey.query.filter_by(
        id=key_id, 
        user_id=current_user.id
    ).first_or_404()
    
    # إلغاء تنشيط المفتاح
    api_key.is_active = False
    db.session.commit()
    
    # تسجيل الحدث
    log_audit_event(
        event_type=EVENT_TYPES['SECURITY'],
        severity=SEVERITY_LEVELS['INFO'],
        details=f"إلغاء تنشيط مفتاح API رقم: {api_key.id}",
        user_id=current_user.id,
        username=current_user.username,
        ip_address=request.remote_addr
    )
    
    flash('تم إلغاء تنشيط المفتاح بنجاح', 'success')
    return redirect(url_for('api_keys'))


@app.route('/admin/referrals')
@admin_required
def admin_referrals():
    """إدارة الإحالات ومراقبة النشاط المشبوه"""
    # الحصول على الإحالات المشبوهة
    suspicious_referrals = Referral.query.filter_by(is_suspicious=True).order_by(desc(Referral.created_at)).all()
    
    # الحصول على الإحالات المعلقة
    pending_referrals = Referral.query.filter_by(status='pending').order_by(desc(Referral.created_at)).all()
    
    # الحصول على عناوين IP المحظورة
    blocked_ips = ReferralIPLog.query.filter_by(is_blocked=True).order_by(desc(ReferralIPLog.last_seen)).all()
    
    # الحصول على الإشعارات غير المقروءة
    unread_notifications = AdminNotification.query.filter_by(is_read=False).order_by(desc(AdminNotification.created_at)).all()
    
    # التحقق من الإحالات المعلقة التي قد تكون تجاوزت مدة التحقق
    checked_count = referral_security.check_pending_verifications()
    if checked_count > 0:
        flash(f'تم فحص {checked_count} من الإحالات المعلقة التي تجاوزت مدة التحقق', 'info')
    
    return render_template(
        'admin/referrals.html',
        suspicious_referrals=suspicious_referrals,
        pending_referrals=pending_referrals,
        blocked_ips=blocked_ips,
        notifications=unread_notifications
    )


@app.route('/admin/referrals/verify/<int:referral_id>')
@admin_required
def admin_verify_referral(referral_id):
    """التحقق اليدوي من إحالة بواسطة المشرف"""
    success = referral_security.verify_referral(referral_id, "admin_verification")
    
    if success:
        flash('تم التحقق من الإحالة وإضافة المكافأة بنجاح', 'success')
    else:
        flash('حدث خطأ أثناء محاولة التحقق من الإحالة', 'danger')
    
    return redirect(url_for('admin_referrals'))


@app.route('/admin/referrals/reject/<int:referral_id>')
@admin_required
def admin_reject_referral(referral_id):
    """رفض إحالة بواسطة المشرف"""
    reason = request.args.get('reason', 'رفض يدوي بواسطة المشرف')
    success = referral_security.reject_referral(referral_id, reason)
    
    if success:
        flash('تم رفض الإحالة بنجاح', 'success')
    else:
        flash('حدث خطأ أثناء محاولة رفض الإحالة', 'danger')
    
    return redirect(url_for('admin_referrals'))


@app.route('/admin/referrals/notification/<int:notification_id>/mark-read')
@admin_required
def admin_mark_notification_read(notification_id):
    """تعليم إشعار كمقروء"""
    notification = AdminNotification.query.get_or_404(notification_id)
    notification.is_read = True
    db.session.commit()
    
    return redirect(url_for('admin_referrals'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's ongoing competitions
    ongoing_participations = Participation.query.filter_by(
        user_id=current_user.id, 
        completed=False
    ).join(Competition).filter(
        Competition.end_date >= datetime.utcnow()
    ).all()
    
    # Get user's completed competitions
    completed_participations = Participation.query.filter_by(
        user_id=current_user.id, 
        completed=True
    ).all()
    
    # Get user's redeemed rewards
    reward_redemptions = RewardRedemption.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(RewardRedemption.created_at)).all()
    
    return render_template(
        'dashboard.html',
        ongoing_participations=ongoing_participations,
        completed_participations=completed_participations,
        reward_redemptions=reward_redemptions
    )


@app.route('/competitions')
def competitions():
    now = datetime.utcnow()
    
    active_competitions = Competition.query.filter(
        Competition.is_active == True,
        Competition.end_date >= now
    ).order_by(Competition.start_date).all()
    
    past_competitions = Competition.query.filter(
        Competition.end_date < now
    ).order_by(desc(Competition.end_date)).limit(5).all()
    
    return render_template(
        'competitions.html',
        active_competitions=active_competitions,
        past_competitions=past_competitions,
        utcnow=now
    )


@app.route('/competitions/<int:competition_id>', methods=['GET', 'POST'])
def competition_details(competition_id):
    try:
        competition = Competition.query.get(competition_id)
        if not competition:
            flash('لم يتم العثور على المسابقة المطلوبة', 'warning')
            return redirect(url_for('competitions'))
        
        # Check if user already participated
        participation = None
        if current_user.is_authenticated:
            participation = Participation.query.filter_by(
                user_id=current_user.id,
                competition_id=competition.id
            ).first()
        
        form = ParticipationForm()
        if current_user.is_authenticated and form.validate_on_submit():
            if not participation:
                # إنشاء سجل المشاركة
                participation = Participation(
                    user_id=current_user.id,
                    competition_id=competition.id
                )
                db.session.add(participation)
                db.session.commit()
                flash('تمت المشاركة في المسابقة بنجاح', 'success')
                
                # التحقق من وجود إحالة معلقة للمستخدم
                if config.REFERRAL_REQUIRE_COMPETITION_PARTICIPATION:
                    # البحث عن إحالة معلقة حيث المستخدم هو المُحال
                    pending_referral = Referral.query.filter_by(
                        referred_id=current_user.id,
                        status='pending',
                        is_verified=False
                    ).first()
                    
                    if pending_referral:
                        # تحقق من الإحالة باستخدام المشاركة في المسابقة
                        successful = referral_security.verify_referral(
                            pending_referral.id, 
                            "competition_participation"
                        )
                        
                        if successful:
                            # إشعار المستخدم بتفعيل الإحالة
                            flash('تم تفعيل رابط الإحالة الخاص بك وتلقى صديقك المكافأة!', 'success')
                
                return redirect(url_for('competition_details', competition_id=competition.id))
            else:
                flash('أنت مشارك بالفعل في هذه المسابقة', 'info')
        
        # Get top participants
        top_participants = Participation.query.filter_by(
            competition_id=competition.id
        ).order_by(desc(Participation.score)).limit(10).all()
        
        # Get competition questions
        questions = []
        if participation:  # Only show questions to participants
            questions = competition.get_questions()
        
        # Get current date for template comparisons
        now = datetime.utcnow()
        
        return render_template(
            'competition_details.html',
            competition=competition,
            participation=participation,
            form=form,
            questions=questions,
            top_participants=top_participants,
            now=now  # Pass current date to template
        )
    except Exception as e:
        app.logger.error(f"Error in competition_details: {str(e)}")
        flash('حدث خطأ أثناء محاولة عرض تفاصيل المسابقة', 'danger')
        return redirect(url_for('competitions'))


