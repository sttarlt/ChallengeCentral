"""
ترحيل لإضافة حقل is_active إلى نموذج Question

هذا الملف يقوم بإضافة حقل جديد يسمى is_active إلى جدول question
لتمكين تعطيل الأسئلة بدلاً من حذفها بشكل كامل.
"""

import datetime
import os
import sys
from sqlalchemy import create_engine, text, MetaData, Table, Column, Boolean
from sqlalchemy.exc import SQLAlchemyError

# الحصول على سلسلة الاتصال بقاعدة البيانات
DB_URL = os.environ.get('DATABASE_URL')

if not DB_URL:
    print("خطأ: لم يتم العثور على رابط قاعدة البيانات في متغيرات البيئة")
    sys.exit(1)

# إنشاء اتصال بقاعدة البيانات
engine = create_engine(DB_URL)

try:
    # التحقق مما إذا كان العمود موجودًا بالفعل
    with engine.connect() as conn:
        # التحقق من وجود عمود is_active
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='question' AND column_name='is_active'"))
        column_exists = result.fetchone() is not None
        
        # إذا لم يكن العمود موجودًا، نقوم بإضافته
        if not column_exists:
            print("إضافة عمود is_active إلى جدول question...")
            
            # إنشاء الترحيل باستخدام SQL
            conn.execute(text("ALTER TABLE question ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
            conn.commit()
            
            # تحديث القيم للأسئلة الحالية
            conn.execute(text("UPDATE question SET is_active = TRUE"))
            conn.commit()
            
            print("تم إضافة عمود is_active بنجاح وتم ضبط القيمة الافتراضية إلى TRUE")
        else:
            print("عمود is_active موجود بالفعل في جدول question")
            
except SQLAlchemyError as e:
    print(f"خطأ في قاعدة البيانات: {e}")
    sys.exit(1)