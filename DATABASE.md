# توصيات قاعدة البيانات لمنصة "مسابقاتي"

## الوضع الحالي
تستخدم المنصة حاليًا قاعدة بيانات PostgreSQL مستضافة على خدمة Neon. هذا خيار جيد للمشاريع الناشئة والمتوسطة الحجم.

## خطة الترقية عند زيادة عدد المستخدمين

### عند 1,000 مستخدم نشط شهريًا

#### 1. تحسين الاستعلامات
- **إضافة الفهارس**: أضف فهارس للحقول المستخدمة بكثرة في البحث والترتيب:

```sql
-- فهرس للبحث عن المستخدمين
CREATE INDEX idx_user_username ON "user" (username);
CREATE INDEX idx_user_email ON "user" (email);

-- فهارس للمعاملات
CREATE INDEX idx_transactions_user_id ON points_transaction (user_id);
CREATE INDEX idx_transactions_created_at ON points_transaction (created_at);
CREATE INDEX idx_transactions_type ON points_transaction (transaction_type);

-- فهارس للإحالات
CREATE INDEX idx_referrals_referrer_id ON referral (referrer_id);
CREATE INDEX idx_referrals_referred_id ON referral (referred_id);
CREATE INDEX idx_referrals_created_at ON referral (created_at);

-- فهارس للمسابقات
CREATE INDEX idx_competitions_is_active ON competition (is_active);
CREATE INDEX idx_competitions_end_date ON competition (end_date);

-- فهارس للمكافآت
CREATE INDEX idx_rewards_is_available ON reward (is_available);
```

#### 2. ضبط إعدادات قاعدة البيانات
- زيادة `shared_buffers` إلى 25% من ذاكرة الخادم
- زيادة `effective_cache_size` إلى 75% من ذاكرة الخادم
- ضبط `max_connections` إلى قيمة مناسبة (عادة 100-200)

### عند 10,000 مستخدم نشط شهريًا

#### 1. ترقية الخطة
- الانتقال إلى خطة أعلى في Neon أو خدمة PostgreSQL متخصصة أخرى لزيادة موارد قاعدة البيانات

#### 2. تقسيم البيانات
- تقسيم جداول المعاملات والإحالات حسب التاريخ:

```sql
-- مثال: إنشاء جدول للمعاملات القديمة
CREATE TABLE points_transaction_archive (LIKE points_transaction INCLUDING ALL);

-- نقل البيانات القديمة
INSERT INTO points_transaction_archive
SELECT * FROM points_transaction
WHERE created_at < (CURRENT_DATE - INTERVAL '1 year');

-- حذف البيانات المنقولة
DELETE FROM points_transaction
WHERE created_at < (CURRENT_DATE - INTERVAL '1 year');
```

#### 3. استخدام التخزين المؤقت
- إضافة Redis للتخزين المؤقت

```python
from flask_caching import Cache

cache = Cache(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/0'
})

# مثال على استخدام التخزين المؤقت
@app.route('/competitions')
@cache.cached(timeout=300)  # تخزين مؤقت لمدة 5 دقائق
def competitions():
    # ...
```

### عند 100,000 مستخدم نشط شهريًا

#### 1. توزيع الحمل
- استخدام قواعد بيانات متعددة: قاعدة بيانات للقراءة وأخرى للكتابة
- تكوين PostgreSQL للنسخ المتماثل (replication)

#### 2. تجزئة النظام
- تقسيم التطبيق إلى خدمات مصغرة (microservices)
- تخصيص قاعدة بيانات منفصلة لكل خدمة

## خطة النسخ الاحتياطي

### 1. النسخ الاحتياطي التلقائي اليومي

أنشئ سكربت `backup.py` لعمل نسخة احتياطية يومية:

```python
import os
import subprocess
from datetime import datetime

# إعدادات النسخ الاحتياطي
BACKUP_DIR = "/path/to/backups"
DB_URL = os.environ.get("DATABASE_URL")
MAX_BACKUPS = 30  # الاحتفاظ بآخر 30 نسخة احتياطية

# إنشاء مجلد النسخ الاحتياطي إذا لم يكن موجودًا
os.makedirs(BACKUP_DIR, exist_ok=True)

# اسم ملف النسخة الاحتياطية
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file = os.path.join(BACKUP_DIR, f"musabaqati_backup_{timestamp}.sql")

# عمل نسخة احتياطية
try:
    subprocess.run(
        ["pg_dump", "-f", backup_file, DB_URL],
        check=True
    )
    print(f"تم إنشاء النسخة الاحتياطية بنجاح: {backup_file}")
    
    # حذف النسخ الاحتياطية القديمة
    backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) 
                      if f.startswith("musabaqati_backup_") and f.endswith(".sql")])
    
    if len(backups) > MAX_BACKUPS:
        for old_backup in backups[:-MAX_BACKUPS]:
            os.remove(old_backup)
            print(f"تم حذف النسخة الاحتياطية القديمة: {old_backup}")
            
except Exception as e:
    print(f"خطأ في إنشاء النسخة الاحتياطية: {str(e)}")
```

### 2. جدولة النسخ الاحتياطي

#### باستخدام cron (Linux/macOS)
```
0 2 * * * /usr/bin/python3 /path/to/backup.py
```

#### باستخدام Task Scheduler (Windows)
1. افتح Task Scheduler
2. أنشئ مهمة جديدة
3. حدد البرنامج: `python.exe`
4. حدد الوسائط: `/path/to/backup.py`
5. حدد الجدول الزمني: كل يوم الساعة 2 صباحًا

### 3. استراتيجية النسخ الاحتياطي المتكاملة

1. **النسخ الاحتياطي اليومي**: احتفظ بنسخة يومية لمدة شهر
2. **النسخ الاحتياطي الأسبوعي**: احتفظ بنسخة أسبوعية لمدة 3 أشهر
3. **النسخ الاحتياطي الشهري**: احتفظ بنسخة شهرية لمدة سنة
4. **تخزين خارجي**: نقل النسخ الاحتياطية إلى تخزين سحابي آمن مثل AWS S3 أو Google Cloud Storage

### 4. اختبار النسخ الاحتياطية

من المهم اختبار استعادة النسخ الاحتياطية بشكل دوري:

```bash
# استعادة نسخة احتياطية لقاعدة بيانات تجريبية
psql -d musabaqati_test -f /path/to/backup_file.sql
```

## مراقبة أداء قاعدة البيانات

### 1. أدوات المراقبة

- **pgBadger**: لتحليل سجلات PostgreSQL
- **pg_stat_statements**: لتتبع الاستعلامات البطيئة
- **Prometheus + Grafana**: لمراقبة الأداء في الوقت الفعلي

### 2. المقاييس الرئيسية للمراقبة

- استخدام وحدة المعالجة المركزية
- استخدام الذاكرة
- معدل I/O لقرص التخزين
- معدل الاتصالات
- وقت الاستجابة للاستعلامات
- متوسط وقت الاستعلام
- معدل ضرب/فشل التخزين المؤقت

## التوصيات الأمنية لقاعدة البيانات

1. **المصادقة الآمنة**:
   - استخدم كلمات مرور قوية
   - استخدم SSL للاتصال بقاعدة البيانات

2. **إدارة الصلاحيات**:
   - إنشاء مستخدمين منفصلين للتطبيق مع صلاحيات محدودة
   - تجنب استخدام المستخدم الرئيسي (postgres) للتطبيق

3. **النسخ الاحتياطي والاستعادة**:
   - تشفير النسخ الاحتياطية
   - تخزين النسخ الاحتياطية في مواقع متعددة

4. **التدقيق والمراقبة**:
   - تمكين تسجيل الأحداث
   - مراقبة الأنشطة المشبوهة