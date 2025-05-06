"""
ملف تكوين Gunicorn للتطبيق
يضمن تشغيل الخادم على المنفذ 8080 المطلوب من قبل Replit
"""
import os
import multiprocessing

# تكوين المنفذ
bind = "0.0.0.0:8080"

# عدد العمليات المتوازية
workers = multiprocessing.cpu_count() * 2 + 1

# إعادة تحميل الكود عند التغيير
reload = True

# تمكين تخزين العملية المؤقت
preload_app = True

# تعيين متغيرات البيئة
raw_env = ["PORT=8080"]

# تكوين السجلات
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"