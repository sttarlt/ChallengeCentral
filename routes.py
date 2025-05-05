from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import desc, func
from app import app, db
from models import User, Competition, Reward, Participation, RewardRedemption
from forms import (
    LoginForm, RegistrationForm, CompetitionForm, RewardForm,
    ParticipationForm, RedeemRewardForm, RedemptionStatusForm
)
from datetime import datetime


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
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('تم إنشاء حسابك بنجاح! يمكنك الآن تسجيل الدخول', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))


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
    active_competitions = Competition.query.filter(
        Competition.is_active == True,
        Competition.end_date >= datetime.utcnow()
    ).order_by(Competition.start_date).all()
    
    past_competitions = Competition.query.filter(
        Competition.end_date < datetime.utcnow()
    ).order_by(desc(Competition.end_date)).limit(5).all()
    
    return render_template(
        'competitions.html',
        active_competitions=active_competitions,
        past_competitions=past_competitions
    )


@app.route('/competitions/<int:competition_id>', methods=['GET', 'POST'])
def competition_details(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
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
            participation = Participation(
                user_id=current_user.id,
                competition_id=competition.id
            )
            db.session.add(participation)
            db.session.commit()
            flash('تمت المشاركة في المسابقة بنجاح', 'success')
            return redirect(url_for('competition_details', competition_id=competition.id))
        else:
            flash('أنت مشارك بالفعل في هذه المسابقة', 'info')
    
    # Get top participants
    top_participants = Participation.query.filter_by(
        competition_id=competition.id
    ).order_by(desc(Participation.score)).limit(10).all()
    
    return render_template(
        'competition_details.html',
        competition=competition,
        participation=participation,
        form=form,
        top_participants=top_participants
    )


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
        if not reward.is_available or reward.quantity <= 0:
            flash('هذه الجائزة غير متاحة حالياً', 'danger')
        elif current_user.points < reward.points_required:
            flash('ليس لديك نقاط كافية لاستبدال هذه الجائزة', 'danger')
        else:
            redemption = RewardRedemption(
                user_id=current_user.id,
                reward_id=reward.id,
                points_spent=reward.points_required,
                status='pending'
            )
            
            # Reduce user points
            current_user.use_points(reward.points_required)
            
            # Reduce reward quantity
            reward.quantity -= 1
            if reward.quantity <= 0:
                reward.is_available = False
            
            db.session.add(redemption)
            db.session.commit()
            
            flash('تم استبدال الجائزة بنجاح! سيتم التواصل معك قريباً', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('rewards.html', reward=reward, form=form)


@app.route('/leaderboard')
def leaderboard():
    top_users = User.query.filter(User.is_admin == False).order_by(User.points.desc()).limit(50).all()
    return render_template('leaderboard.html', top_users=top_users)


# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    total_users = User.query.filter_by(is_admin=False).count()
    total_competitions = Competition.query.count()
    active_competitions = Competition.query.filter_by(is_active=True).count()
    total_rewards = Reward.query.count()
    
    recent_redemptions = RewardRedemption.query.order_by(
        desc(RewardRedemption.created_at)
    ).limit(10).all()
    
    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_competitions=total_competitions,
        active_competitions=active_competitions,
        total_rewards=total_rewards,
        recent_redemptions=recent_redemptions
    )


@app.route('/admin/competitions', methods=['GET'])
@login_required
def admin_competitions():
    if not current_user.is_admin:
        abort(403)
    
    competitions = Competition.query.order_by(desc(Competition.created_at)).all()
    return render_template('admin/competitions.html', competitions=competitions)


@app.route('/admin/competitions/new', methods=['GET', 'POST'])
@login_required
def admin_new_competition():
    if not current_user.is_admin:
        abort(403)
    
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
@login_required
def admin_edit_competition(competition_id):
    if not current_user.is_admin:
        abort(403)
    
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
@login_required
def admin_rewards():
    if not current_user.is_admin:
        abort(403)
    
    rewards = Reward.query.order_by(desc(Reward.created_at)).all()
    return render_template('admin/rewards.html', rewards=rewards)


@app.route('/admin/rewards/new', methods=['GET', 'POST'])
@login_required
def admin_new_reward():
    if not current_user.is_admin:
        abort(403)
    
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
@login_required
def admin_edit_reward(reward_id):
    if not current_user.is_admin:
        abort(403)
    
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


@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    
    users = User.query.filter_by(is_admin=False).order_by(desc(User.created_at)).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/redemptions', methods=['GET'])
@login_required
def admin_redemptions():
    if not current_user.is_admin:
        abort(403)
    
    redemptions = RewardRedemption.query.order_by(desc(RewardRedemption.created_at)).all()
    return render_template('admin/redemptions.html', redemptions=redemptions)


@app.route('/admin/redemptions/<int:redemption_id>', methods=['GET', 'POST'])
@login_required
def admin_update_redemption(redemption_id):
    if not current_user.is_admin:
        abort(403)
    
    redemption = RewardRedemption.query.get_or_404(redemption_id)
    form = RedemptionStatusForm(obj=redemption)
    
    if form.validate_on_submit():
        redemption.status = form.status.data
        db.session.commit()
        flash('تم تحديث حالة الاستبدال بنجاح', 'success')
        return redirect(url_for('admin_redemptions'))
    
    return render_template('admin/redemptions.html', form=form, redemption=redemption)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500
