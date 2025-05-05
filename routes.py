from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import desc, func, or_
from functools import wraps
from app import app, db
from models import User, Competition, Reward, Participation, RewardRedemption, ChatRoom, ChatRoomMember, Message, PointsPackage
import config
from forms import (
    LoginForm, RegistrationForm, CompetitionForm, RewardForm,
    ParticipationForm, RedeemRewardForm, RedemptionStatusForm,
    CreateChatRoomForm, SendMessageForm, DirectMessageForm
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
