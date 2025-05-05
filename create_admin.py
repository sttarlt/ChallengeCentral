from app import app, db
from models import User

with app.app_context():
    # Check if admin user already exists
    admin = User.query.filter_by(is_admin=True).first()
    
    if not admin:
        # Create a new admin user
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        # استخدام الطريقة المعرفة في نموذج User لتعيين كلمة المرور
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully!')
        print('Username: admin, Email: admin@example.com, Password: admin123')
    else:
        print('Admin user already exists:')
        print(f'Username: {admin.username}, Email: {admin.email}')