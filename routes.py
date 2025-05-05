from flask import render_template, redirect, url_for, flash, request, abort, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import desc, func, or_
from functools import wraps
from app import app, db
from models import User, Competition, Reward, Participation, RewardRedemption, ChatRoom, ChatRoomMember, Message, PointsPackage, Referral, ReferralIPLog, AdminNotification
import config
import referral_security
from forms import (
    LoginForm, RegistrationForm, CompetitionForm, RewardForm,
    ParticipationForm, RedeemRewardForm, RedemptionStatusForm,
    CreateChatRoomForm, SendMessageForm, DirectMessageForm,
    PointsPackageForm, AdminPointsForm
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


@app.route('/')
def index():
    active_competitions = Competition.query.filter(
        Competition.is_active == True,
        Competition.end_date >= datetime.utcnow()
    ).order_by(Competition.start_date).limit(4).all()
    
    popular_rewards = Reward.query.filter_by(is_available=True).order_by(
        Reward.points_required
    ).limit(4).all()
    
    top_users = User.query.order_by(User.points.desc()).limit(5).all()
    
    return render_template(
        'index.html',
        competitions=active_competitions,
        rewards=popular_rewards,
        top_users=top_users
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect(next_page or url_for('dashboard'))
        flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
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
            
            # منح المكافأة الترحيبية للمستخدم الجديد (هذه تُمنح فوراً)
            welcome_bonus = config.REFERRAL_WELCOME_BONUS
            if welcome_bonus > 0:
                user.add_points(welcome_bonus)
                flash(f'تهانينا! لقد حصلت على {welcome_bonus} كربتو كمكافأة ترحيبية', 'success')
            
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
        
        # Get current date for template comparisons
        now = datetime.utcnow()
        
        return render_template(
            'competition_details.html',
            competition=competition,
            participation=participation,
            form=form,
            top_participants=top_participants,
            now=now  # Pass current date to template
        )
    except Exception as e:
        app.logger.error(f"Error in competition_details: {str(e)}")
        flash('حدث خطأ أثناء محاولة عرض تفاصيل المسابقة', 'danger')
        return redirect(url_for('competitions'))


@app.route('/rewards')
def rewards():
    available_rewards = Reward.query.filter_by(is_available=True).all()
    return render_template('rewards.html', rewards=available_rewards)


@app.route('/rewards/redeem/<int:reward_id>', methods=['GET', 'POST'])
@login_required
def redeem_reward(reward_id):
    reward = Reward.query.get_or_404(reward_id)
    form = RedeemRewardForm()
    
    if form.validate_on_submit():
        # التحقق من صحة CSRF Token
        if not form.validate_csrf_token(form.csrf_token):
            flash('خطأ في التحقق من طلبك. يرجى المحاولة مرة أخرى.', 'danger')
            return redirect(url_for('rewards'))
            
        # التحقق من توفر الجائزة
        if not reward.is_available or reward.quantity <= 0:
            flash('هذه الجائزة غير متاحة حالياً', 'danger')
            return redirect(url_for('rewards'))
            
        # التحقق من وجود نقاط كافية
        if current_user.points < reward.points_required:
            flash('ليس لديك كربتو كافٍ لاستبدال هذه الجائزة', 'danger')
            return redirect(url_for('rewards'))
            
        # إنشاء سجل استبدال الجائزة
        redemption = RewardRedemption(
            user_id=current_user.id,
            reward_id=reward.id,
            points_spent=reward.points_required,
            status='pending'
        )
        db.session.add(redemption)
        
        # تسجيل وخصم النقاط باستخدام النظام الجديد
        # نلاحظ أننا نمرر كائن الطلب request لتسجيل عنوان IP والمتصفح
        # ونحدد نوع المعاملة وسبب الخصم ومعرف الجائزة
        success = current_user.use_points(
            reward.points_required,
            transaction_type='reward_redemption',
            related_id=reward.id,
            description=f'استبدال جائزة: {reward.name}',
            request=request
        )
        
        if not success:
            # في حالة فشل العملية (نادر الحدوث، ولكن للأمان)
            db.session.rollback()
            flash('حدث خطأ أثناء محاولة استبدال الجائزة. يرجى المحاولة مرة أخرى.', 'danger')
            return redirect(url_for('rewards'))
            
        # تقليل كمية الجائزة المتاحة
        reward.quantity -= 1
        if reward.quantity <= 0:
            reward.is_available = False
        
        db.session.commit()
        
        flash('تم استبدال الجائزة بنجاح! سيتم التواصل معك قريباً', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('rewards.html', reward=reward, form=form)


@app.route('/leaderboard')
def leaderboard():
    top_users = User.query.filter(User.is_admin == False).order_by(User.points.desc()).limit(50).all()
    return render_template('leaderboard.html', top_users=top_users)


@app.route('/points-pricing')
def points_pricing():
    """عرض صفحة باقات الكربتو وأسعارها"""
    packages = PointsPackage.query.filter_by(is_active=True).order_by(PointsPackage.display_order).all()
    contact_link = config.CONTACT_LINK
    currency_name = config.CURRENCY_NAME
    currency_name_plural = config.CURRENCY_NAME_PLURAL
    return render_template('points_pricing.html', 
                          packages=packages, 
                          contact_link=contact_link,
                          currency_name=currency_name,
                          currency_name_plural=currency_name_plural)


# Admin routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # إذا كان المستخدم مسجل دخول بالفعل كمشرف، يتم توجيهه إلى لوحة التحكم مباشرة
    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    
    # إذا كان المستخدم مسجل دخول كمستخدم عادي، نقوم بتسجيل خروجه أولاً
    if current_user.is_authenticated:
        logout_user()
        flash('تم تسجيل خروجك. يرجى تسجيل الدخول كمشرف', 'info')
    
    form = LoginForm()
    if form.validate_on_submit():
        app.logger.debug(f"Login attempt with email: {form.email.data}")
        
        # البحث عن المستخدم بالبريد الإلكتروني
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            app.logger.debug(f"User found: {user.username}, is_admin: {user.is_admin}")
            
            # التحقق من كلمة المرور
            if user.check_password(form.password.data):
                app.logger.debug("Password check passed")
                
                # التحقق من أن المستخدم هو مشرف
                if user.is_admin:
                    app.logger.debug("User is admin, logging in")
                    login_user(user)
                    app.logger.debug(f"User logged in: {current_user.username}, is_authenticated: {current_user.is_authenticated}")
                    flash('تم تسجيل الدخول كمشرف بنجاح', 'success')
                    return redirect(url_for('admin_dashboard'))
                else:
                    app.logger.debug("User is not admin")
                    app.logger.warning(f"Non-admin user {user.username} attempted to access admin panel")
                    flash('حسابك ليس لديه صلاحيات مشرف. يرجى التواصل مع إدارة النظام إذا كنت تعتقد أن هذا خطأ.', 'danger')
                    return redirect(url_for('index'))
            else:
                app.logger.debug("Password check failed")
                flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
        else:
            app.logger.debug(f"No user found with email: {form.email.data}")
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('admin/login.html', form=form)


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    
    # جمع إحصائيات للوحة التحكم
    total_users = User.query.filter_by(is_admin=False).count()
    total_competitions = Competition.query.count()
    active_competitions = Competition.query.filter_by(is_active=True).count()
    total_rewards = Reward.query.count()
    
    recent_redemptions = RewardRedemption.query.order_by(
        desc(RewardRedemption.created_at)
    ).limit(10).all()
    
    # طباعة معلومات التصحيح
    app.logger.debug(f"Admin dashboard accessed by: {current_user.username}, is_admin: {current_user.is_admin}")
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_competitions=total_competitions,
        active_competitions=active_competitions,
        total_rewards=total_rewards,
        recent_redemptions=recent_redemptions
    )


@app.route('/admin/competitions', methods=['GET'])
@admin_required
def admin_competitions():
    
    competitions = Competition.query.order_by(desc(Competition.created_at)).all()
    return render_template('admin/competitions.html', competitions=competitions)


@app.route('/admin/competitions/new', methods=['GET', 'POST'])
@admin_required
def admin_new_competition():
    
    form = CompetitionForm()
    if form.validate_on_submit():
        competition = Competition(
            title=form.title.data,
            description=form.description.data,
            points=form.points.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            is_active=form.is_active.data
        )
        db.session.add(competition)
        db.session.commit()
        flash('تم إنشاء المسابقة بنجاح', 'success')
        return redirect(url_for('admin_competitions'))
    
    return render_template('admin/competitions.html', form=form)


@app.route('/admin/competitions/edit/<int:competition_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_competition(competition_id):
    
    competition = Competition.query.get_or_404(competition_id)
    form = CompetitionForm(obj=competition)
    
    if form.validate_on_submit():
        competition.title = form.title.data
        competition.description = form.description.data
        competition.points = form.points.data
        competition.start_date = form.start_date.data
        competition.end_date = form.end_date.data
        competition.is_active = form.is_active.data
        
        db.session.commit()
        flash('تم تحديث المسابقة بنجاح', 'success')
        return redirect(url_for('admin_competitions'))
    
    return render_template('admin/competitions.html', form=form, competition=competition)


@app.route('/admin/rewards', methods=['GET'])
@admin_required
def admin_rewards():
    
    rewards = Reward.query.order_by(desc(Reward.created_at)).all()
    return render_template('admin/rewards.html', rewards=rewards)


@app.route('/admin/rewards/new', methods=['GET', 'POST'])
@admin_required
def admin_new_reward():
    
    form = RewardForm()
    if form.validate_on_submit():
        reward = Reward(
            name=form.name.data,
            description=form.description.data,
            points_required=form.points_required.data,
            quantity=form.quantity.data,
            is_available=form.is_available.data
        )
        db.session.add(reward)
        db.session.commit()
        flash('تم إنشاء الجائزة بنجاح', 'success')
        return redirect(url_for('admin_rewards'))
    
    return render_template('admin/rewards.html', form=form)


@app.route('/admin/rewards/edit/<int:reward_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_reward(reward_id):
    
    reward = Reward.query.get_or_404(reward_id)
    form = RewardForm(obj=reward)
    
    if form.validate_on_submit():
        reward.name = form.name.data
        reward.description = form.description.data
        reward.points_required = form.points_required.data
        reward.quantity = form.quantity.data
        reward.is_available = form.is_available.data
        
        db.session.commit()
        flash('تم تحديث الجائزة بنجاح', 'success')
        return redirect(url_for('admin_rewards'))
    
    return render_template('admin/rewards.html', form=form, reward=reward)


@app.route('/admin/points-packages', methods=['GET'])
@admin_required
def admin_points_packages():
    """إدارة باقات الكربتو"""
    packages = PointsPackage.query.order_by(PointsPackage.display_order).all()
    contact_link = config.CONTACT_LINK
    currency_name = config.CURRENCY_NAME
    currency_name_plural = config.CURRENCY_NAME_PLURAL
    return render_template('admin/points_packages.html', 
                          packages=packages, 
                          contact_link=contact_link,
                          currency_name=currency_name,
                          currency_name_plural=currency_name_plural)


@app.route('/admin/points-packages/new', methods=['GET', 'POST'])
@admin_required
def admin_new_points_package():
    """إضافة باقة كربتو جديدة"""
    form = PointsPackageForm()
    currency_name = config.CURRENCY_NAME
    currency_name_plural = config.CURRENCY_NAME_PLURAL
    
    if form.validate_on_submit():
        package = PointsPackage(
            name=form.name.data,
            price=form.price.data,
            points=form.points.data,
            description=form.description.data,
            is_active=form.is_active.data,
            display_order=form.display_order.data
        )
        db.session.add(package)
        db.session.commit()
        flash(f'تم إضافة باقة ال{currency_name} بنجاح', 'success')
        return redirect(url_for('admin_points_packages'))
    
    return render_template('admin/points_packages.html', 
                          form=form, 
                          currency_name=currency_name, 
                          currency_name_plural=currency_name_plural)


@app.route('/admin/points-packages/edit/<int:package_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_points_package(package_id):
    """تعديل باقة كربتو"""
    package = PointsPackage.query.get_or_404(package_id)
    form = PointsPackageForm(obj=package)
    currency_name = config.CURRENCY_NAME
    currency_name_plural = config.CURRENCY_NAME_PLURAL
    
    if form.validate_on_submit():
        package.name = form.name.data
        package.price = form.price.data
        package.points = form.points.data
        package.description = form.description.data
        package.is_active = form.is_active.data
        package.display_order = form.display_order.data
        
        db.session.commit()
        flash(f'تم تحديث باقة ال{currency_name} بنجاح', 'success')
        return redirect(url_for('admin_points_packages'))
    
    return render_template('admin/points_packages.html', 
                          form=form, 
                          package=package,
                          currency_name=currency_name,
                          currency_name_plural=currency_name_plural)


@app.route('/admin/config', methods=['GET', 'POST'])
@admin_required
def admin_config():
    """تعديل إعدادات النظام"""
    
    if request.method == 'POST':
        new_contact_link = request.form.get('contact_link')
        
        # Update the config.py file (we're doing this by modifying and writing to the file directly)
        with open('config.py', 'r') as file:
            lines = file.readlines()
        
        with open('config.py', 'w') as file:
            for line in lines:
                if 'CONTACT_LINK' in line:
                    file.write(f'CONTACT_LINK = "{new_contact_link}"\n')
                else:
                    file.write(line)
        
        # Reload config
        import importlib
        importlib.reload(config)
        
        flash('تم تحديث إعدادات النظام بنجاح', 'success')
        return redirect(url_for('admin_config'))
    
    return render_template('admin/config.html', contact_link=config.CONTACT_LINK)


@app.route('/admin/users', methods=['GET'])
@admin_required
def admin_users():
    
    users = User.query.filter_by(is_admin=False).order_by(desc(User.created_at)).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/redemptions', methods=['GET'])
@admin_required
def admin_redemptions():
    
    redemptions = RewardRedemption.query.order_by(desc(RewardRedemption.created_at)).all()
    return render_template('admin/redemptions.html', redemptions=redemptions)


@app.route('/admin/redemptions/<int:redemption_id>', methods=['GET', 'POST'])
@admin_required
def admin_update_redemption(redemption_id):
    
    redemption = RewardRedemption.query.get_or_404(redemption_id)
    form = RedemptionStatusForm(obj=redemption)
    
    if form.validate_on_submit():
        redemption.status = form.status.data
        db.session.commit()
        flash('تم تحديث حالة الاستبدال بنجاح', 'success')
        return redirect(url_for('admin_redemptions'))
    
    return render_template('admin/redemptions.html', form=form, redemption=redemption)


@app.route('/admin/transactions')
@admin_required
def admin_transactions():
    """عرض سجل معاملات الكربتو مع إمكانية البحث والتصفية"""
    from models import PointsTransaction
    
    # استخراج معايير البحث من البارامترات
    user_id = request.args.get('user_id', type=int)
    transaction_type = request.args.get('transaction_type')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    per_page = 50  # عدد العناصر في كل صفحة
    
    # إنشاء الاستعلام الأساسي
    query = PointsTransaction.query
    
    # تطبيق المرشحات إذا كانت موجودة
    if user_id:
        query = query.filter(PointsTransaction.user_id == user_id)
    
    if transaction_type:
        query = query.filter(PointsTransaction.transaction_type == transaction_type)
    
    # تطبيق نطاق التاريخ
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(PointsTransaction.created_at >= start_date)
        except ValueError:
            flash('صيغة تاريخ البداية غير صحيحة، تم تجاهلها', 'warning')
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            # إضافة يوم كامل لتضمين كل معاملات اليوم المحدد
            end_date = end_date.replace(hour=23, minute=59, second=59)
            query = query.filter(PointsTransaction.created_at <= end_date)
        except ValueError:
            flash('صيغة تاريخ النهاية غير صحيحة، تم تجاهلها', 'warning')
    
    # ترتيب النتائج من الأحدث إلى الأقدم
    query = query.order_by(PointsTransaction.created_at.desc())
    
    # تنفيذ الاستعلام مع التقسيم إلى صفحات
    pagination = query.paginate(page=page, per_page=per_page)
    transactions = pagination.items
    
    return render_template(
        'admin/transactions.html',
        transactions=transactions,
        pagination=pagination
    )


@app.route('/admin/transactions/user/<int:user_id>')
@admin_required
def admin_user_transactions(user_id):
    """عرض سجل معاملات الكربتو لمستخدم محدد"""
    from models import PointsTransaction
    
    # التحقق من وجود المستخدم
    user = User.query.get_or_404(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = 20  # عدد العناصر في كل صفحة
    
    # الحصول على معاملات المستخدم
    query = PointsTransaction.query.filter_by(user_id=user_id).order_by(PointsTransaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page)
    transactions = pagination.items
    
    return render_template(
        'admin/transactions.html',
        transactions=transactions,
        pagination=pagination,
        user=user
    )


@app.route('/admin/add-points', methods=['GET', 'POST'])
@admin_required
def admin_add_points():
    """إضافة أو خصم كربتو لمستخدم من قبل المشرف"""
    from models import PointsTransaction
    
    form = AdminPointsForm()
    
    if form.validate_on_submit():
        # البحث عن المستخدم بواسطة اسم المستخدم
        user = User.query.filter_by(username=form.username.data).first()
        
        if not user:
            flash(f'لم يتم العثور على المستخدم: {form.username.data}', 'danger')
            return redirect(url_for('admin_add_points'))
        
        points = form.points.data
        description = form.description.data
        notify_user = form.notify_user.data
        
        # التحقق مما إذا كانت العملية إضافة أو خصم
        if points > 0:
            # إضافة نقاط
            success = user.add_points(
                points=points, 
                transaction_type='admin_adjustment',
                description=description,
                created_by_id=current_user.id,
                request=request
            )
            
            if success:
                flash(f'تم إضافة {points} كربتو إلى حساب {user.username} بنجاح', 'success')
                app.logger.info(f"Admin {current_user.username} added {points} points to user {user.username}")
            else:
                flash('حدث خطأ أثناء محاولة إضافة النقاط', 'danger')
        
        elif points < 0:
            # خصم نقاط (تحويل إلى رقم موجب للتمرير إلى دالة use_points)
            absolute_points = abs(points)
            
            # التحقق من كفاية الرصيد
            if user.points < absolute_points:
                flash(f'لا يملك المستخدم {user.username} رصيد كاف. الرصيد الحالي: {user.points} كربتو', 'danger')
                return redirect(url_for('admin_add_points'))
            
            success = user.use_points(
                points=absolute_points, 
                transaction_type='admin_adjustment',
                description=description,
                created_by_id=current_user.id,
                request=request
            )
            
            if success:
                flash(f'تم خصم {absolute_points} كربتو من حساب {user.username} بنجاح', 'success')
                app.logger.info(f"Admin {current_user.username} deducted {absolute_points} points from user {user.username}")
            else:
                flash('حدث خطأ أثناء محاولة خصم النقاط', 'danger')
        
        else:
            # لا تغيير (صفر نقاط)
            flash('لم يتم تنفيذ أي تغيير، تم إدخال صفر نقاط', 'warning')
            
        # إعادة توجيه إلى صفحة معاملات المستخدم
        return redirect(url_for('admin_user_transactions', user_id=user.id))
    
    return render_template('admin/add_points.html', form=form)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# Chat routes
@app.route('/chat')
@login_required
def chat_rooms():
    """Show all chat rooms the user is part of, plus public rooms they can join."""
    # Get all chat rooms the user is a member of
    user_chat_memberships = ChatRoomMember.query.filter_by(user_id=current_user.id).all()
    user_chat_room_ids = [membership.chat_room_id for membership in user_chat_memberships]
    
    # Get those chat rooms
    user_chat_rooms = ChatRoom.query.filter(ChatRoom.id.in_(user_chat_room_ids)).all()
    
    # Get direct message rooms
    direct_message_rooms = [room for room in user_chat_rooms if room.is_direct_message]
    
    # Get group chat rooms
    group_chat_rooms = [room for room in user_chat_rooms if not room.is_direct_message]
    
    # Get public chat rooms user is not part of
    other_public_rooms = ChatRoom.query.filter(
        ~ChatRoom.id.in_(user_chat_room_ids),
        ChatRoom.is_direct_message == False
    ).all()
    
    # Form for creating a new chat room
    create_form = CreateChatRoomForm()
    
    # Form for sending direct message
    dm_form = DirectMessageForm()
    
    return render_template(
        'chat/rooms.html', 
        direct_message_rooms=direct_message_rooms,
        group_chat_rooms=group_chat_rooms,
        other_public_rooms=other_public_rooms,
        create_form=create_form,
        dm_form=dm_form
    )


@app.route('/chat/rooms/create', methods=['POST'])
@login_required
def create_chat_room():
    """Create a new chat room."""
    form = CreateChatRoomForm()
    if form.validate_on_submit():
        # Create new chat room
        chat_room = ChatRoom(
            name=form.name.data,
            description=form.description.data,
            is_direct_message=False
        )
        db.session.add(chat_room)
        db.session.commit()
        
        # Add the creator as a member and admin
        member = ChatRoomMember(
            user_id=current_user.id,
            chat_room_id=chat_room.id,
            is_admin=True
        )
        db.session.add(member)
        db.session.commit()
        
        flash('تم إنشاء غرفة الدردشة بنجاح!', 'success')
        return redirect(url_for('chat_room', room_id=chat_room.id))
    
    # If validation failed, flash errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    
    return redirect(url_for('chat_rooms'))


@app.route('/chat/rooms/<int:room_id>', methods=['GET', 'POST'])
@login_required
def chat_room(room_id):
    """Display a chat room and handle posting messages."""
    chat_room = ChatRoom.query.get_or_404(room_id)
    
    # Check if user is a member of this room
    membership = ChatRoomMember.query.filter_by(
        user_id=current_user.id,
        chat_room_id=chat_room.id
    ).first()
    
    # If not, add them if it's not a direct message room
    if not membership and not chat_room.is_direct_message:
        membership = ChatRoomMember(
            user_id=current_user.id,
            chat_room_id=chat_room.id
        )
        db.session.add(membership)
        db.session.commit()
    elif not membership and chat_room.is_direct_message:
        # If it's a direct message room and user is not a member, they shouldn't see it
        abort(403)
    
    # Update last read timestamp
    membership.last_read_at = datetime.utcnow()
    db.session.commit()
    
    # Get all messages in this room
    messages = Message.query.filter_by(
        chat_room_id=chat_room.id
    ).order_by(Message.created_at).all()
    
    # Get all members of this room
    members = User.query.join(ChatRoomMember).filter(
        ChatRoomMember.chat_room_id == chat_room.id
    ).all()
    
    # Form for sending messages
    form = SendMessageForm()
    if form.validate_on_submit():
        message = Message(
            chat_room_id=chat_room.id,
            sender_id=current_user.id,
            content=form.content.data
        )
        
        # If it's a direct message, set the recipient
        if chat_room.is_direct_message:
            # Find the other user in the room
            other_member = ChatRoomMember.query.filter(
                ChatRoomMember.chat_room_id == chat_room.id,
                ChatRoomMember.user_id != current_user.id
            ).first()
            
            if other_member:
                message.recipient_id = other_member.user_id
        
        db.session.add(message)
        db.session.commit()
        
        # Redirect to avoid form resubmission
        return redirect(url_for('chat_room', room_id=chat_room.id))
    
    return render_template(
        'chat/room.html',
        chat_room=chat_room,
        messages=messages,
        members=members,
        form=form
    )


@app.route('/chat/join/<int:room_id>')
@login_required
def join_chat_room(room_id):
    """Join a chat room."""
    chat_room = ChatRoom.query.get_or_404(room_id)
    
    # Check if user is already a member
    existing_membership = ChatRoomMember.query.filter_by(
        user_id=current_user.id,
        chat_room_id=chat_room.id
    ).first()
    
    if existing_membership:
        flash('أنت بالفعل عضو في هذه الغرفة', 'info')
    else:
        # Add user as a member
        member = ChatRoomMember(
            user_id=current_user.id,
            chat_room_id=chat_room.id
        )
        db.session.add(member)
        db.session.commit()
        flash('تم الانضمام للغرفة بنجاح!', 'success')
    
    return redirect(url_for('chat_room', room_id=chat_room.id))


@app.route('/chat/direct-message', methods=['POST'])
@login_required
def send_direct_message():
    """Start a direct message conversation with another user."""
    form = DirectMessageForm()
    if form.validate_on_submit():
        # Find the recipient user
        recipient = User.query.filter_by(username=form.recipient_username.data).first()
        
        if not recipient:
            flash('لم يتم العثور على المستخدم', 'danger')
            return redirect(url_for('chat_rooms'))
        
        # Check if there's already a DM room between these users
        # Get all rooms where both users are members
        sender_rooms = ChatRoomMember.query.filter_by(user_id=current_user.id).with_entities(ChatRoomMember.chat_room_id).subquery()
        recipient_rooms = ChatRoomMember.query.filter_by(user_id=recipient.id).with_entities(ChatRoomMember.chat_room_id).subquery()
        
        common_rooms = ChatRoom.query.filter(
            ChatRoom.id.in_(sender_rooms),
            ChatRoom.id.in_(recipient_rooms),
            ChatRoom.is_direct_message == True
        ).first()
        
        if common_rooms:
            # If they already have a DM room, use that
            chat_room = common_rooms
        else:
            # Create a new DM room
            room_name = f"محادثة بين {current_user.username} و {recipient.username}"
            chat_room = ChatRoom(
                name=room_name,
                is_direct_message=True
            )
            db.session.add(chat_room)
            db.session.commit()
            
            # Add both users as members
            sender_member = ChatRoomMember(
                user_id=current_user.id,
                chat_room_id=chat_room.id
            )
            recipient_member = ChatRoomMember(
                user_id=recipient.id,
                chat_room_id=chat_room.id
            )
            db.session.add(sender_member)
            db.session.add(recipient_member)
            db.session.commit()
        
        # Create the first message
        message = Message(
            chat_room_id=chat_room.id,
            sender_id=current_user.id,
            recipient_id=recipient.id,
            content=form.content.data
        )
        db.session.add(message)
        db.session.commit()
        
        return redirect(url_for('chat_room', room_id=chat_room.id))
    
    # If validation failed, flash errors
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'danger')
    
    return redirect(url_for('chat_rooms'))

# روابط تحدي الصديق (نظام الإحالة)
@app.route('/invite')
def invite():
    """معالجة رابط الدعوة وتخزين كود الإحالة في الجلسة مع إجراءات الأمان"""
    referral_code = request.args.get('ref')
    
    if referral_code:
        # التحقق من وجود المستخدم المحيل
        referrer = User.query.filter_by(referral_code=referral_code).first()
        
        if referrer:
            # تتبع عنوان IP لمنع التلاعب
            ip_address = request.remote_addr
            user_agent = request.user_agent.string if request.user_agent else None
            
            # فحص عنوان IP للتحقق من أمان الإحالة
            ip_safe, ip_status = referral_security.track_referral_ip(ip_address)
            
            if not ip_safe:
                # توجيه رسالة ملائمة حسب سبب رفض الإحالة
                if ip_status == "ip_blocked":
                    flash('معذرة، تم حظر طلبك بسبب نشاط مشبوه. إذا كنت تعتقد أن هذا خطأ، يرجى التواصل مع الدعم.', 'danger')
                elif ip_status == "max_referrals_per_ip":
                    flash('تم تجاوز الحد المسموح من الإحالات من جهازك خلال 24 ساعة. يرجى المحاولة لاحقًا.', 'warning')
                
                return redirect(url_for('index'))
            
            # فحص نشاط المستخدم المرجع (المحيل) للكشف عن أنماط مشبوهة
            suspicious, reason = referral_security.detect_suspicious_activity(referrer.id)
            
            if suspicious:
                # تسجيل النشاط المشبوه ولكن السماح بمتابعة الإحالة مع وضع علامة عليها
                app.logger.warning(f"Suspicious referral activity detected: User {referrer.username}, reason: {reason}")
                # تخزين معلومات للتحقق لاحقًا
                session['referral_suspicious'] = True
            
            # تخزين كود الإحالة في الجلسة لاستخدامه لاحقاً عند التسجيل
            session['referral_code'] = referral_code
            session['referral_ip'] = ip_address
            session['referral_user_agent'] = user_agent
            
            # إذا كان المستخدم مسجل الدخول بالفعل، فلا يمكن استخدام الإحالة
            if current_user.is_authenticated:
                flash('أنت مسجل الدخول بالفعل ولا يمكنك استخدام رابط الإحالة', 'info')
                return redirect(url_for('dashboard'))
            
            # توجيه المستخدم إلى صفحة التسجيل
            return redirect(url_for('register'))
    
    # إذا لم يتم العثور على كود إحالة صالح، نعود إلى الصفحة الرئيسية
    flash('رابط الإحالة غير صالح', 'warning')
    return redirect(url_for('index'))


@app.route('/friend-challenge')
@login_required
def friend_challenge():
    """صفحة تحدي الصديق (نظام الإحالة)"""
    # التأكد من وجود كود إحالة للمستخدم وإنشاؤه إذا لم يكن موجوداً
    if not current_user.referral_code:
        current_user.generate_referral_code()
        db.session.commit()
    
    # الحصول على رابط الإحالة الكامل
    referral_url = request.host_url.rstrip('/') + current_user.get_referral_url()
    
    # عدد الأصدقاء الذين تمت إحالتهم
    referred_friends_count = Referral.query.filter_by(referrer_id=current_user.id).count()
    
    # الحصول على معلومات المكافأة القادمة
    next_milestone_info = current_user.get_next_milestone_info()
    
    # معلومات حدود الإحالة
    monthly_limit = config.REFERRAL_MONTHLY_LIMIT
    total_limit = config.REFERRAL_TOTAL_LIMIT
    monthly_used = current_user.monthly_referral_points
    total_used = current_user.total_referral_points
    
    # إذا وصل المستخدم إلى الحد الأقصى
    reached_limit = False
    if current_user.total_referral_points >= total_limit:
        reached_limit = True
    
    # المكافآت
    referral_reward = config.REFERRAL_REWARD_PER_FRIEND
    welcome_bonus = config.REFERRAL_WELCOME_BONUS
    milestone_rewards = config.REFERRAL_MILESTONE_REWARDS
    
    return render_template(
        'friend_challenge.html',
        referral_url=referral_url,
        referred_friends_count=referred_friends_count,
        total_referral_points=current_user.total_referral_points,
        next_milestone_info=next_milestone_info,
        monthly_limit=monthly_limit,
        total_limit=total_limit,
        monthly_used=monthly_used,
        total_used=total_used,
        reached_limit=reached_limit,
        referral_reward=referral_reward,
        welcome_bonus=welcome_bonus,
        milestone_rewards=milestone_rewards
    )
