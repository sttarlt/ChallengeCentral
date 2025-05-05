from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField, BooleanField, DateTimeField, SelectField, FloatField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from models import User


class LoginForm(FlaskForm):
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    submit = SubmitField('تسجيل الدخول')


class RegistrationForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('إنشاء حساب')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('اسم المستخدم مستخدم بالفعل، يرجى اختيار اسم آخر.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('البريد الإلكتروني مستخدم بالفعل، يرجى استخدام بريد آخر.')


class CompetitionForm(FlaskForm):
    title = StringField('عنوان المسابقة', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('وصف المسابقة', validators=[DataRequired()])
    points = IntegerField('الكربتو', validators=[DataRequired()])
    start_date = DateTimeField('تاريخ البدء', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_date = DateTimeField('تاريخ الانتهاء', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    is_active = BooleanField('نشط')
    submit = SubmitField('حفظ المسابقة')


class RewardForm(FlaskForm):
    name = StringField('اسم الجائزة', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('وصف الجائزة', validators=[DataRequired()])
    points_required = IntegerField('الكربتو المطلوبة', validators=[DataRequired()])
    quantity = IntegerField('الكمية', validators=[DataRequired()])
    is_available = BooleanField('متاح')
    submit = SubmitField('حفظ الجائزة')


class ParticipationForm(FlaskForm):
    submit = SubmitField('المشاركة في المسابقة')


class RedeemRewardForm(FlaskForm):
    submit = SubmitField('استبدال الجائزة')


class RedemptionStatusForm(FlaskForm):
    status = SelectField('الحالة', choices=[('pending', 'قيد الانتظار'), ('completed', 'مكتمل'), ('cancelled', 'ملغي')])
    submit = SubmitField('تحديث الحالة')


class CreateChatRoomForm(FlaskForm):
    name = StringField('اسم الغرفة', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('وصف الغرفة')
    submit = SubmitField('إنشاء غرفة دردشة')


class SendMessageForm(FlaskForm):
    content = TextAreaField('الرسالة', validators=[DataRequired()])
    submit = SubmitField('إرسال')


class DirectMessageForm(FlaskForm):
    recipient_username = StringField('اسم المستخدم', validators=[DataRequired()])
    content = TextAreaField('الرسالة', validators=[DataRequired()])
    submit = SubmitField('إرسال رسالة خاصة')
    
    def validate_recipient_username(self, recipient_username):
        user = User.query.filter_by(username=recipient_username.data).first()
        if not user:
            raise ValidationError('لم يتم العثور على هذا المستخدم.')


class PointsPackageForm(FlaskForm):
    name = StringField('اسم الباقة', validators=[DataRequired(), Length(max=50)])
    price = FloatField('السعر (دولار)', validators=[DataRequired(), NumberRange(min=0.1)])
    points = IntegerField('الكربتو', validators=[DataRequired(), NumberRange(min=1)])
    description = StringField('وصف مختصر', validators=[Length(max=255)])
    is_active = BooleanField('نشط')
    display_order = IntegerField('ترتيب العرض', validators=[DataRequired()], default=0)
    submit = SubmitField('حفظ الباقة')


class AdminPointsForm(FlaskForm):
    """نموذج تعديل نقاط المستخدم من قبل المشرف"""
    username = StringField('اسم المستخدم', validators=[DataRequired()])
    points = IntegerField('عدد النقاط', validators=[DataRequired()])
    description = StringField('السبب', validators=[DataRequired(), Length(max=255)])
    notify_user = BooleanField('إشعار المستخدم')
    submit = SubmitField('تعديل الرصيد')
