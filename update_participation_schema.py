#!/usr/bin/env python
"""
سكريبت لتحديث جدول المشاركة لإضافة العمود الجديد completed_at
"""
import sys
import os
import logging
from datetime import datetime

# تكوين سجل الأحداث
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# التأكد من تنفيذ السكريبت من الدليل الرئيسي للمشروع
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from app import app, db
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    logger.info("تم استيراد المكتبات بنجاح")
except ImportError as e:
    logger.error(f"خطأ في استيراد المكتبات: {e}")
    sys.exit(1)

def check_column_exists(table, column):
    """التحقق مما إذا كان العمود موجودًا في الجدول"""
    with app.app_context():
        try:
            # استعلام لفحص وجود العمود في جدول محدد
            query = text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = '{column}'
            """)
            result = db.session.execute(query).fetchone()
            return result is not None
        except SQLAlchemyError as e:
            logger.error(f"خطأ في فحص وجود العمود: {e}")
            return False

def add_column_if_not_exists(table, column, column_type):
    """إضافة عمود إلى الجدول إذا لم يكن موجودًا"""
    if not check_column_exists(table, column):
        with app.app_context():
            try:
                logger.info(f"إضافة العمود {column} إلى الجدول {table}")
                query = text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                db.session.execute(query)
                db.session.commit()
                logger.info(f"تم إضافة العمود {column} بنجاح")
                return True
            except SQLAlchemyError as e:
                db.session.rollback()
                logger.error(f"خطأ في إضافة العمود: {e}")
                return False
    else:
        logger.info(f"العمود {column} موجود بالفعل في الجدول {table}")
        return False

def main():
    """الدالة الرئيسية لتحديث قاعدة البيانات"""
    try:
        logger.info("بدء تحديث جدول المشاركة")
        
        # إضافة العمود completed_at إلى جدول participation
        add_column_if_not_exists('participation', 'completed_at', 'TIMESTAMP')
        
        # تحديث جميع المشاركات التي لديها completed = True ولكن لا يوجد لديها completed_at
        with app.app_context():
            query = text("""
                UPDATE participation 
                SET completed_at = NOW() 
                WHERE completed = TRUE AND completed_at IS NULL
            """)
            result = db.session.execute(query)
            db.session.commit()
            logger.info(f"تم تحديث {result.rowcount} سجل من سجلات المشاركة")
        
        logger.info("تم تحديث قاعدة البيانات بنجاح")
    except Exception as e:
        logger.error(f"خطأ أثناء تحديث قاعدة البيانات: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())