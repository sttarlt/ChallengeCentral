"""
نموذج لملف إعدادات السرية
قم بنسخ هذا الملف إلى config_secrets.py وتعديل القيم حسب بيئة التشغيل
تأكد من عدم رفع ملف config_secrets.py إلى مستودع Git
"""

# مفتاح سري للتطبيق (يجب تغييره في بيئة الإنتاج)
SECRET_KEY = "generate-a-secure-random-key-here"

# إعدادات قاعدة البيانات
DATABASE_URI = "postgresql://username:password@localhost/db_name"

# إعدادات البريد الإلكتروني
MAIL_SERVER = "smtp.example.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "your-email@example.com"
MAIL_PASSWORD = "your-email-password"
MAIL_DEFAULT_SENDER = "no-reply@example.com"

# رابط التواصل مع المشرف للشراء
CONTACT_LINK = "https://t.me/your_telegram_username"