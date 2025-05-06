"""
هذا هو نقطة الدخول الرئيسية للتطبيق على Replit.
يقوم بتشغيل التطبيق على المنفذ 8080 المطلوب من قبل Replit.
"""
import os
import sys
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# استيراد التطبيق
try:
    from app import app
    import routes  # noqa: F401
    import api_routes  # noqa: F401
except ImportError as e:
    logger.error(f"خطأ في استيراد التطبيق: {e}")
    sys.exit(1)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"بدء الخادم على المنفذ {port}")
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"خطأ في تشغيل التطبيق: {e}")
        sys.exit(1)