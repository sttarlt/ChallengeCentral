from app import app, db
from models import User
from sqlalchemy import text

with app.app_context():
    # تحديث المشرف القديم بدلاً من حذفه لتجنب مشاكل المفاتيح الأجنبية
    old_admin = User.query.filter_by(email='admin@example.com').first()
    if old_admin:
        print('تم العثور على حساب المشرف القديم، جاري تحديث بياناته...')
        old_admin.email = 'ltsttar00@gmail.com'
        old_admin.set_password('Agyy6655')
        db.session.commit()
        print('تم تحديث بيانات المشرف بنجاح.')
        print(f'البريد الإلكتروني الجديد: {old_admin.email}')
    else:
        # التحقق من وجود المشرف الجديد
        new_admin = User.query.filter_by(email='ltsttar00@gmail.com').first()
        
        if not new_admin:
            # إنشاء مشرف جديد بالبيانات المحدثة
            new_admin = User(
                username='admin',
                email='ltsttar00@gmail.com',
                is_admin=True
            )
            # استخدام الطريقة المعرفة في نموذج User لتعيين كلمة المرور الجديدة
            new_admin.set_password('Agyy6655')
            db.session.add(new_admin)
            db.session.commit()
            print('تم إنشاء حساب المشرف الجديد بنجاح!')
            print('البريد الإلكتروني: ltsttar00@gmail.com')
        else:
            # تحديث كلمة مرور المشرف الجديد إذا كان موجوداً
            new_admin.set_password('Agyy6655')
            db.session.commit()
            print('تم تحديث بيانات المشرف:')
            print(f'اسم المستخدم: {new_admin.username}, البريد الإلكتروني: {new_admin.email}')