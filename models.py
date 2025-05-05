from app import db, app
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


class PointsTransaction(db.Model):
    """سجل جميع عمليات تعديل رصيد الكربتو"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # مقدار النقاط (موجب للإضافة، سالب للخصم)
    balance_after = db.Column(db.Integer, nullable=False)  # الرصيد بعد العملية
    transaction_type = db.Column(db.String(50), nullable=False)  # نوع العملية (مكافأة، استبدال، إحالة، إلخ)
    related_id = db.Column(db.Integer, nullable=True)  # معرف المرتبط (مثل معرف المكافأة أو الإحالة)
    description = db.Column(db.String(255), nullable=True)  # وصف مختصر للعملية
    ip_address = db.Column(db.String(45), nullable=True)  # عنوان IP
    user_agent = db.Column(db.String(255), nullable=True)  # معلومات المتصفح
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # من قام بإنشاء العملية (المستخدم نفسه أو المشرف)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], backref='transactions')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<PointsTransaction {self.id}: {self.amount} for user {self.user_id}>'


class PurchaseRecord(db.Model):
    """سجل عمليات شراء الكربتو"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)  # المبلغ المدفوع بالدولار
    currency = db.Column(db.String(10), default='USD')  # عملة الدفع
    points_added = db.Column(db.Integer, nullable=False)  # كمية الكربتو المضافة
    payment_method = db.Column(db.String(50), nullable=True)  # طريقة الدفع (تلغرام، تحويل بنكي، إلخ)
    reference = db.Column(db.String(255), nullable=True)  # مرجع الدفع أو رقم المعاملة
    notes = db.Column(db.Text, nullable=True)  # ملاحظات إضافية
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # المشرف الذي أضاف العملية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # وقت العملية
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], backref='purchases')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<PurchaseRecord {self.id}: ${self.amount_paid} for {self.points_added} points by user {self.user_id}>'


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
    
    def add_points(self, points, transaction_type, related_id=None, description=None, created_by_id=None, request=None):
        """
        إضافة نقاط للمستخدم مع تسجيل العملية
        
        Args:
            points (int): عدد النقاط المراد إضافتها
            transaction_type (str): نوع العملية (مكافأة، إحالة، إلخ)
            related_id (int): معرف مرتبط (مثل معرف المكافأة أو الإحالة)
            description (str): وصف مختصر للعملية
            created_by_id (int): معرف المستخدم الذي أنشأ العملية (المستخدم نفسه أو المشرف)
            request (Flask.request): كائن الطلب للحصول على معلومات مثل IP و User-Agent
        """
        if points <= 0:
            return False
            
        try:
            # إضافة النقاط للمستخدم
            self.points += points
            
            # إنشاء سجل العملية
            transaction = PointsTransaction(
                user_id=self.id,
                amount=points,
                balance_after=self.points,
                transaction_type=transaction_type,
                related_id=related_id,
                description=description,
                created_by_id=created_by_id or self.id
            )
            
            # إضافة معلومات الطلب إذا كانت متوفرة
            if request:
                transaction.ip_address = self.get_client_ip(request)
                transaction.user_agent = request.user_agent.string
            
            db.session.add(transaction)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"خطأ في إضافة النقاط: {str(e)}")
            return False
    
    def get_client_ip(self, request):
        """
        الحصول على عنوان IP الحقيقي للعميل بشكل آمن
        مع مراعاة الوسطاء والشبكات العكسية
        """
        if 'X-Forwarded-For' in request.headers:
            # تقسيم سلسلة العناوين واختيار أول عنصر (عنوان العميل الأصلي)
            x_forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            if x_forwarded_for:
                # التحقق من صحة تنسيق IP (يجب إضافة تحقق أكثر تفصيلاً)
                if len(x_forwarded_for) <= 45:  # الحد الأقصى لطول IPv6
                    return x_forwarded_for
        
        # إذا لم يكن هناك X-Forwarded-For، استخدم remote_addr
        return request.remote_addr
    
    def use_points(self, points, transaction_type, related_id=None, description=None, created_by_id=None, request=None):
        """
        استخدام نقاط من رصيد المستخدم مع تسجيل العملية
        
        Args:
            points (int): عدد النقاط المراد استخدامها
            transaction_type (str): نوع العملية (استبدال جائزة، إلخ)
            related_id (int): معرف مرتبط (مثل معرف الجائزة)
            description (str): وصف مختصر للعملية
            created_by_id (int): معرف المستخدم الذي أنشأ العملية (المستخدم نفسه أو المشرف)
            request (Flask.request): كائن الطلب للحصول على معلومات مثل IP و User-Agent
        """
        if points <= 0 or self.points < points:
            return False
            
        try:
            # خصم النقاط من المستخدم
            self.points -= points
            
            # إنشاء سجل العملية
            transaction = PointsTransaction(
                user_id=self.id,
                amount=-points,  # قيمة سالبة للخصم
                balance_after=self.points,
                transaction_type=transaction_type,
                related_id=related_id,
                description=description,
                created_by_id=created_by_id or self.id
            )
            
            # إضافة معلومات الطلب إذا كانت متوفرة
            if request:
                transaction.ip_address = self.get_client_ip(request)
                transaction.user_agent = request.user_agent.string
            
            db.session.add(transaction)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"خطأ في استخدام النقاط: {str(e)}")
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
        from flask import url_for
        if not self.referral_code:
            self.generate_referral_code()
        return url_for('invite', ref=self.referral_code, _external=True)
    
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
    
    def add_referral_points(self, points, referral_id=None, request=None):
        """إضافة نقاط إحالة مع مراعاة الحدود"""
        can_receive, actual_points = self.can_receive_referral_reward(points)
        
        if isinstance(actual_points, (int, float)) and actual_points > 0:
            # استخدام الدالة المحسنة لإضافة النقاط مع تسجيل العملية
            self.add_points(
                actual_points, 
                transaction_type='referral_reward',
                related_id=referral_id,
                description=f'مكافأة إحالة - {actual_points} كربتو',
                request=request
            )
            
            # تحديث عدادات الإحالة
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


class SystemConfig(db.Model):
    """نموذج لتخزين إعدادات النظام في قاعدة البيانات بدلاً من الملف"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)  # اسم الإعداد
    value = db.Column(db.Text, nullable=True)  # قيمة الإعداد
    description = db.Column(db.String(255), nullable=True)  # وصف الإعداد
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # وقت آخر تحديث
    
    def __repr__(self):
        return f'<SystemConfig {self.key}={self.value}>'
    
    @classmethod
    def get(cls, key, default=None):
        """الحصول على قيمة إعداد معين مع إعداد افتراضي"""
        config = cls.query.filter_by(key=key).first()
        if config:
            return config.value
        return default
    
    @classmethod
    def set(cls, key, value, description=None):
        """تعيين قيمة إعداد معين"""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = cls(key=key, value=value, description=description)
            db.session.add(config)
        db.session.commit()
        return config
