from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email='ltsttar00@gmail.com').first()
    
    if user:
        print(f'المستخدم موجود: نعم')
        print(f'اسم المستخدم: {user.username}')
        print(f'البريد الإلكتروني: {user.email}')
        print(f'هل هو مشرف؟: {user.is_admin}')
        print(f'تجزئة كلمة المرور: {user.password_hash[:20]}...')
        print(f'التحقق من كلمة المرور "Agyy6655": {user.check_password("Agyy6655")}')
    else:
        print('المستخدم غير موجود! يرجى تشغيل create_admin.py لإنشاء حساب المشرف.')