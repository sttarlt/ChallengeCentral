from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Check if admin user already exists
    admin = User.query.filter_by(is_admin=True).first()
    
    if not admin:
        # Create a new admin user
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully!')
    else:
        print('Admin user already exists:')
        print(f'Username: {admin.username}, Email: {admin.email}')