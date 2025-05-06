"""
سكريبت تحديث قاعدة البيانات لإضافة الحقول الجديدة لنظام المسابقات المحسن
يقوم بإضافة الأعمدة الجديدة إلى جدول Competition وQuestion وParticipation
دون فقدان البيانات الموجودة

للتنفيذ:
python update_competition_schema.py
"""

import os
import sys
import logging
from datetime import datetime

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/db_migration.log', 'a')
    ]
)
logger = logging.getLogger(__name__)

try:
    from flask import Flask
    from sqlalchemy import create_engine, text, Column, Integer, Float, Boolean, String, Text, DateTime
    from sqlalchemy.exc import SQLAlchemyError, OperationalError
    from app import db, app
except ImportError as e:
    logger.error(f"فشل استيراد المكتبات المطلوبة: {e}")
    sys.exit(1)

def check_column_exists(table, column):
    """التحقق مما إذا كان العمود موجودًا في الجدول"""
    try:
        with db.engine.connect() as connection:
            query = text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name = '{column}'
            """)
            result = connection.execute(query)
            return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error(f"خطأ أثناء التحقق من وجود العمود {column} في الجدول {table}: {e}")
        return False

def add_column_if_not_exists(table, column, column_type):
    """إضافة عمود إلى الجدول إذا لم يكن موجودًا"""
    if not check_column_exists(table, column):
        try:
            with db.engine.connect() as connection:
                query = text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                connection.execute(query)
                connection.commit()
                logger.info(f"تم إضافة العمود {column} إلى الجدول {table}")
                return True
        except SQLAlchemyError as e:
            logger.error(f"خطأ أثناء إضافة العمود {column} إلى الجدول {table}: {e}")
            return False
    else:
        logger.info(f"العمود {column} موجود بالفعل في الجدول {table}")
        return True

def main():
    """الدالة الرئيسية لتحديث قاعدة البيانات"""
    logger.info("=== بدء تحديث هيكل قاعدة البيانات ===")
    
    with app.app_context():
        # تنظيف أي معاملات معلقة
        try:
            db.session.rollback()
            db.session.close()
            db.session.remove()
            logger.info("تم تنظيف المعاملات المعلقة")
        except Exception as e:
            logger.error(f"خطأ أثناء تنظيف المعاملات: {e}")
        
        # إضافة الحقول الجديدة إلى جدول Competition
        competition_columns = [
            ("time_limit", "INTEGER"),
            ("randomize_questions", "BOOLEAN DEFAULT FALSE"),
            ("show_results_immediately", "BOOLEAN DEFAULT TRUE"),
            ("allow_multiple_attempts", "BOOLEAN DEFAULT FALSE"),
            ("penalty_for_wrong_answers", "INTEGER DEFAULT 0"),
            ("bonus_points", "INTEGER DEFAULT 0")
        ]
        
        for col_name, col_type in competition_columns:
            add_column_if_not_exists("competition", col_name, col_type)
        
        # إضافة الحقول الجديدة إلى جدول Question
        question_columns = [
            ("explanation", "TEXT"),
            ("base_points", "INTEGER DEFAULT 1"),
            ("time_bonus_enabled", "BOOLEAN DEFAULT FALSE"),
            ("time_bonus_factor", "FLOAT DEFAULT 0.5"),
            ("partial_credit_enabled", "BOOLEAN DEFAULT FALSE")
        ]
        
        for col_name, col_type in question_columns:
            add_column_if_not_exists("question", col_name, col_type)
        
        # تحديث حقل points في Question ليكون base_points لدعم الترحيل
        try:
            with db.engine.connect() as connection:
                query = text("""
                    UPDATE question 
                    SET base_points = points 
                    WHERE base_points IS NULL OR base_points = 0
                """)
                connection.execute(query)
                connection.commit()
                logger.info("تم تحديث base_points من قيم points الحالية")
        except SQLAlchemyError as e:
            logger.error(f"خطأ أثناء تحديث base_points: {e}")
        
        # إضافة الحقول الجديدة إلى جدول Participation
        participation_columns = [
            ("completion_time", "INTEGER"),
            ("attempts", "INTEGER DEFAULT 1"),
            ("last_attempt_at", "TIMESTAMP"),
            ("answers_data", "TEXT"),
            ("correct_answers", "INTEGER DEFAULT 0"),
            ("bonus_points", "INTEGER DEFAULT 0"),
            ("penalties", "INTEGER DEFAULT 0"),
            ("time_bonus", "INTEGER DEFAULT 0")
        ]
        
        for col_name, col_type in participation_columns:
            add_column_if_not_exists("participation", col_name, col_type)
        
        logger.info("=== اكتمل تحديث هيكل قاعدة البيانات ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"خطأ غير متوقع أثناء التحديث: {e}")
        sys.exit(1)