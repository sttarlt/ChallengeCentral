"""
سكريبت لتحديث جدول الأسئلة بإضافة الأعمدة الجديدة المفقودة
"""
import os

from app import app, db
from flask import Flask
from sqlalchemy import text

def update_question_table():
    """إضافة الأعمدة المفقودة إلى جدول الأسئلة"""
    print("بدء عملية تحديث جدول الأسئلة...")
    
    with app.app_context():
        # التحقق من وجود الأعمدة
        columns_to_add = []
        
        # إستعلام لمعرفة هل توجد الأعمدة بالفعل
        conn = db.engine.connect()
        
        try:
            # التحقق من وجود عمود image_url
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='question' AND column_name='image_url'"))
            if result.rowcount == 0:
                columns_to_add.append("image_url")
                print("- سيتم إضافة عمود image_url")
            
            # التحقق من وجود عمود time_limit
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='question' AND column_name='time_limit'"))
            if result.rowcount == 0:
                columns_to_add.append("time_limit")
                print("- سيتم إضافة عمود time_limit")
                
            # التحقق من وجود عمود difficulty
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='question' AND column_name='difficulty'"))
            if result.rowcount == 0:
                columns_to_add.append("difficulty")
                print("- سيتم إضافة عمود difficulty")
            
            # إضافة الأعمدة المفقودة
            if "image_url" in columns_to_add:
                conn.execute(text("ALTER TABLE question ADD COLUMN image_url VARCHAR(500)"))
                print("✓ تمت إضافة عمود image_url")
                
            if "time_limit" in columns_to_add:
                conn.execute(text("ALTER TABLE question ADD COLUMN time_limit INTEGER"))
                print("✓ تمت إضافة عمود time_limit")
                
            if "difficulty" in columns_to_add:
                conn.execute(text("ALTER TABLE question ADD COLUMN difficulty VARCHAR(20) DEFAULT 'medium'"))
                print("✓ تمت إضافة عمود difficulty")
            
            # إنهاء المعاملة إذا تم إضافة عمود واحد على الأقل
            if columns_to_add:
                print("\nتم تحديث جدول الأسئلة بنجاح!")
            else:
                print("\nجميع الأعمدة المطلوبة موجودة بالفعل في الجدول.")
                
        except Exception as e:
            print(f"حدث خطأ أثناء تحديث جدول الأسئلة: {str(e)}")
        finally:
            conn.close()
            
if __name__ == "__main__":
    update_question_table()