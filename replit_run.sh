#!/bin/bash

# هذا الملف مخصص لتشغيل التطبيق على منصة Replit
# يقوم بتشغيل التطبيق على المنفذ 8080 للتوافق مع متطلبات Replit

# تعيين متغيرات البيئة
export PORT=8080

# تشغيل الخادم
echo "Starting server on PORT $PORT at $(date)"
exec gunicorn --bind 0.0.0.0:8080 --reuse-port --reload main:app