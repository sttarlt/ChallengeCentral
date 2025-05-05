"""
سكريبت لإنشاء باقات النقاط الافتراضية في قاعدة البيانات
يتم تشغيل هذا السكريبت مرة واحدة فقط عند بدء تشغيل التطبيق لأول مرة
أو عند الرغبة في تحديث/إعادة تعيين باقات النقاط
"""

from app import app, db
from models import PointsPackage

def create_default_packages():
    """إنشاء باقات النقاط الافتراضية"""
    
    # تنظيف الباقات الموجودة حالياً
    PointsPackage.query.delete()
    
    # إنشاء الباقات الافتراضية
    packages = [
        {
            'name': 'Basic Package',
            'price': 1,
            'points': 100,
            'description': 'بداية قوية للمبتدئين',
            'display_order': 1
        },
        {
            'name': 'Standard Package',
            'price': 5,
            'points': 600,
            'description': 'القيمة الأفضل للمستخدمين النشطين',
            'display_order': 2
        },
        {
            'name': 'Premium Package',
            'price': 10,
            'points': 1300,
            'description': 'الباقة المثالية للمتحمسين',
            'display_order': 3
        }
    ]
    
    for package_data in packages:
        package = PointsPackage(
            name=package_data['name'],
            price=package_data['price'],
            points=package_data['points'],
            description=package_data['description'],
            is_active=True,
            display_order=package_data['display_order']
        )
        db.session.add(package)
    
    db.session.commit()
    print("تم إنشاء باقات النقاط الافتراضية بنجاح!")

# عند تشغيل هذا الملف مباشرة
if __name__ == "__main__":
    with app.app_context():
        create_default_packages()