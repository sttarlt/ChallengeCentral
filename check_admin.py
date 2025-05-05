from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(email='admin@example.com').first()
    
    if user:
        print(f'User exists: True')
        print(f'Username: {user.username}')
        print(f'Email: {user.email}')
        print(f'Is admin: {user.is_admin}')
        print(f'Password hash: {user.password_hash[:20]}...')
        print(f'Check password "admin123": {user.check_password("admin123")}')
    else:
        print('User does not exist!')