import os
import logging
import threading
import time
from app import app  # noqa: F401
import api_routes  # noqa: F401
import routes  # noqa: F401

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# دالة للحفاظ على التطبيق قيد التشغيل
def keep_alive():
    """وظيفة تعمل في خلفية لضمان استمرار خادم الويب في العمل."""
    while True:
        logger.info("Keep-alive check - Server is running")
        time.sleep(300)  # التحقق كل 5 دقائق

# تشغيل دالة keep_alive في خلفية
def start_keep_alive():
    """بدء عملية keep-alive في خلفية."""
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True  # سيتوقف الخيط عندما يتوقف البرنامج الرئيسي
    keep_alive_thread.start()
    logger.info("Keep-alive thread started")

if __name__ == "__main__":
    # استخدام المنفذ 8080 (المطلوب في Replit) أو المنفذ المحدد في المتغيرات البيئية
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    
    # تشغيل دالة keep_alive
    start_keep_alive()
    
    # تشغيل التطبيق
    app.run(host="0.0.0.0", port=port, debug=True)
