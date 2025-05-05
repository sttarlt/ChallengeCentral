from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class PointsPackage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PointsPackage {self.name}: ${self.price} = {self.points} points>'


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # حقول نظام الإحالة
    referral_code = db.Column(db.String(16), unique=True, nullable=True)  # كود الإحالة الفريد
    total_referrals = db.Column(db.Integer, default=0)  # إجمالي عدد الإحالات
    monthly_referral_points = db.Column(db.Integer, default=0)  # نقاط الإحالة الشهرية
    total_referral_points = db.Column(db.Integer, default=0)  # إجمالي نقاط الإحالة المكتسبة
    last_referral_reset = db.Column(db.DateTime, default=datetime.utcnow)  # تاريخ آخر إعادة ضبط شهري
    referred_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # من قام بدعوة هذا المستخدم
    
    # العلاقات
    participations = db.relationship('Participation', backref='participant', lazy='dynamic')
    redemptions = db.relationship('RewardRedemption', backref='user', lazy='dynamic')
    # علاقات الدردشة
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    chat_rooms = db.relationship('ChatRoomMember', backref='user', lazy='dynamic')
    # علاقة self للإحالات
    referred_users = db.relationship('User', 
                                    backref=db.backref('referred_by', uselist=False),
                                    remote_side=[id])

    def set_password(self, password):
        """تشفير كلمة المرور"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """التحقق من كلمة المرور"""
        # التحقق من أن password_hash موجود قبل استخدام check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def add_points(self, points):
        self.points += points
        db.session.commit()
    
    def use_points(self, points):
        if self.points >= points:
            self.points -= points
            db.session.commit()
            return True
        return False
    
    def generate_referral_code(self):
        """إنشاء كود إحالة فريد للمستخدم"""
        import string
        import random
        
        if not self.referral_code:
            # إنشاء كود عشوائي من 8 أحرف
            chars = string.ascii_letters + string.digits
            code = ''.join(random.choice(chars) for _ in range(8))
            
            # التأكد من عدم وجود تكرار للكود
            while User.query.filter_by(referral_code=code).first() is not None:
                code = ''.join(random.choice(chars) for _ in range(8))
            
            self.referral_code = code
            db.session.commit()
        
        return self.referral_code
    
    def get_referral_url(self):
        """الحصول على رابط الإحالة الكامل"""
        if not self.referral_code:
            self.generate_referral_code()
        return f"/invite?ref={self.referral_code}"
    
    def can_receive_referral_reward(self, reward_amount):
        """التحقق مما إذا كان المستخدم يمكنه استلام مكافأة إحالة"""
        # إعادة ضبط العداد الشهري إذا مر شهر
        now = datetime.utcnow()
        if (now.year > self.last_referral_reset.year or 
            (now.year == self.last_referral_reset.year and now.month > self.last_referral_reset.month)):
            self.monthly_referral_points = 0
            self.last_referral_reset = now
            db.session.commit()
        
        # التحقق من الحدود الشهرية والإجمالية
        monthly_limit = 500  # الحد الشهري
        total_limit = 1000   # الحد الإجمالي
        
        if self.total_referral_points >= total_limit:
            return False, "total_limit"
        
        if self.monthly_referral_points + reward_amount > monthly_limit:
            # يمكن منح مكافأة جزئية إذا تبقى جزء من الحد الشهري
            if self.monthly_referral_points < monthly_limit:
                return True, monthly_limit - self.monthly_referral_points
            return False, "monthly_limit"
        
        return True, reward_amount
    
    def add_referral_points(self, points):
        """إضافة نقاط إحالة مع مراعاة الحدود"""
        can_receive, actual_points = self.can_receive_referral_reward(points)
        
        if isinstance(actual_points, (int, float)) and actual_points > 0:
            self.add_points(actual_points)
            self.monthly_referral_points += actual_points
            self.total_referral_points += actual_points
            db.session.commit()
            return actual_points
        
        return 0
    
    def get_next_milestone_info(self):
        """الحصول على معلومات المكافأة القادمة"""
        # عدد الإحالات الحالية
        current_referrals = self.total_referrals
        
        # المعالم والمكافآت المرتبطة بها
        milestones = {
            5: 10,   # 5 إحالات = 10 كربتو إضافية
            10: 20,  # 10 إحالات = 20 كربتو إضافية
        }
        
        # البحث عن المعلم التالي
        next_milestone = None
        reward = None
        
        for milestone, milestone_reward in sorted(milestones.items()):
            remaining = milestone - (current_referrals % milestone)
            if remaining < milestone:  # إذا لم يتم الوصول إلى المعلم بعد
                next_milestone = milestone
                reward = milestone_reward
                break
        
        if next_milestone:
            remaining = next_milestone - (current_referrals % next_milestone)
            return {
                'milestone': next_milestone,
                'reward': reward,
                'remaining': remaining
            }
        
        return None


class Competition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    participations = db.relationship('Participation', backref='competition', lazy='dynamic')


class Reward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points_required = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    redemptions = db.relationship('RewardRedemption', backref='reward', lazy='dynamic')


class Participation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RewardRedemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reward_id = db.Column(db.Integer, db.ForeignKey('reward.id'), nullable=False)
    points_spent = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatRoom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_direct_message = db.Column(db.Boolean, default=False)  # True if it's a DM between two users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('ChatRoomMember', backref='chat_room', lazy='dynamic')
    messages = db.relationship('Message', backref='chat_room', lazy='dynamic')
    
    def get_recent_messages(self, limit=20):
        """Get the most recent messages in the chat room."""
        return self.messages.order_by(Message.created_at.desc()).limit(limit).all()[::-1]


class ChatRoomMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Admin of the chat room
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_read_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def has_unread_messages(self):
        """Check if there are unread messages for this member."""
        last_message = self.chat_room.messages.order_by(Message.created_at.desc()).first()
        if last_message and last_message.created_at > self.last_read_at:
            return True
        return False
    
    def unread_count(self):
        """Count the number of unread messages."""
        return self.chat_room.messages.filter(Message.created_at > self.last_read_at).count()


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_room.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Only used for direct messages
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Referral(db.Model):
    """نموذج لتتبع الإحالات بين المستخدمين"""
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, verified, rejected
    reward_paid = db.Column(db.Boolean, default=False)
    reward_amount = db.Column(db.Integer, default=0)  # المبلغ الفعلي المدفوع
    ip_address = db.Column(db.String(45), nullable=True)  # يدعم IPv6
    user_agent = db.Column(db.String(255), nullable=True)  # معلومات المتصفح
    verification_method = db.Column(db.String(50), nullable=True)  # كيف تم التحقق (بريد إلكتروني، مشاركة في مسابقة، إلخ)
    rejection_reason = db.Column(db.String(255), nullable=True)  # سبب رفض الإحالة إذا تم رفضها
    is_suspicious = db.Column(db.Boolean, default=False)  # علامة للنشاط المشبوه
    is_verified = db.Column(db.Boolean, default=False)  # تم التحقق من المستخدم
    verified_at = db.Column(db.DateTime, nullable=True)  # وقت التحقق
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # علاقات قاعدة البيانات
    referrer = db.relationship('User', foreign_keys=[referrer_id], backref='referrals_made')
    referred = db.relationship('User', foreign_keys=[referred_id], backref='referral_source')
    
    def __repr__(self):
        return f'<Referral {self.referrer_id} -> {self.referred_id} ({self.status})>'


class ReferralIPLog(db.Model):
    """سجل عناوين IP للإحالات لمنع التلاعب"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)  # يدعم IPv6
    referral_count = db.Column(db.Integer, default=1)  # عدد الإحالات من نفس الـ IP
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_blocked = db.Column(db.Boolean, default=False)  # حظر عناوين IP المشبوهة
    
    def __repr__(self):
        return f'<ReferralIPLog {self.ip_address} count={self.referral_count}>'


class AdminNotification(db.Model):
    """إشعارات للمشرفين عن النشاط المشبوه"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50), default='suspicious_activity')  # نوع الإشعار
    related_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # المستخدم المتعلق بالإشعار
    related_referral_id = db.Column(db.Integer, db.ForeignKey('referral.id'), nullable=True)  # الإحالة المتعلقة بالإشعار
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # علاقات قاعدة البيانات
    related_user = db.relationship('User', foreign_keys=[related_user_id])
    related_referral = db.relationship('Referral', foreign_keys=[related_referral_id])
    
    def __repr__(self):
        return f'<AdminNotification {self.id}: {self.title[:20]}... ({self.notification_type})>'
