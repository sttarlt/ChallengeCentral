# دليل الأمان لمنصة "مسابقاتي"

هذا الدليل يتضمن إرشادات وتوصيات لتعزيز أمان منصة "مسابقاتي" عند النشر في بيئة الإنتاج.

## 1. حماية البيانات السرية

### إعدادات السرية
- أنشئ ملف `config_secrets.py` بناءً على نموذج `config_example.py` لحفظ البيانات السرية.
- لا ترفع ملف `config_secrets.py` أبدًا إلى مستودع Git.
- استخدم مفتاح سري قوي وفريد لكل بيئة تشغيل.

### متغيرات البيئة
- احرص على تخزين البيانات السرية كمتغيرات بيئية بدلاً من كتابتها في الكود:
  ```
  export SESSION_SECRET="your-secure-secret-key"
  export DATABASE_URL="postgresql://user:password@localhost/dbname"
  ```
- استخدم أداة مثل `python-dotenv` لتحميل متغيرات البيئة من ملف `.env` في بيئة التطوير المحلية.

## 2. إعداد بروتوكول HTTPS

### باستخدام Let's Encrypt مع Nginx

1. **تثبيت Certbot**:
   ```bash
   sudo apt update
   sudo apt install certbot python3-certbot-nginx
   ```

2. **الحصول على شهادة SSL**:
   ```bash
   sudo certbot --nginx -d your-domain.com -d www.your-domain.com
   ```

3. **تكوين Nginx**:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       # إعادة توجيه HTTP إلى HTTPS
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name your-domain.com www.your-domain.com;
       
       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_prefer_server_ciphers on;
       ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
       
       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

4. **التجديد التلقائي**:
   ```bash
   sudo certbot renew --dry-run
   ```
   وأضف مهمة cron للتجديد التلقائي:
   ```
   0 3 * * * /usr/bin/certbot renew --quiet
   ```

### باستخدام Let's Encrypt مع Apache

1. **تثبيت Certbot**:
   ```bash
   sudo apt update
   sudo apt install certbot python3-certbot-apache
   ```

2. **الحصول على شهادة SSL**:
   ```bash
   sudo certbot --apache -d your-domain.com -d www.your-domain.com
   ```

3. **تكوين Apache**:
   ```apache
   <VirtualHost *:80>
       ServerName your-domain.com
       ServerAlias www.your-domain.com
       Redirect permanent / https://your-domain.com/
   </VirtualHost>

   <VirtualHost *:443>
       ServerName your-domain.com
       ServerAlias www.your-domain.com
       
       SSLEngine on
       SSLCertificateFile /etc/letsencrypt/live/your-domain.com/fullchain.pem
       SSLCertificateKeyFile /etc/letsencrypt/live/your-domain.com/privkey.pem
       
       ProxyPreserveHost On
       ProxyPass / http://127.0.0.1:5000/
       ProxyPassReverse / http://127.0.0.1:5000/
       
       RequestHeader set X-Forwarded-Proto "https"
       RequestHeader set X-Forwarded-Port "443"
   </VirtualHost>
   ```

### تكوين SSL على Replit

Replit يدعم HTTPS تلقائيًا لتطبيقات الويب. التطبيق الخاص بك سيكون متاحًا عبر:
```
https://your-app-name.your-username.repl.co
```

للتأكد من استخدام HTTPS، تم إضافة الإعدادات التالية في الكود:
```python
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
```

## 3. تأمين قاعدة البيانات

### تأمين PostgreSQL

1. **استخدم كلمة مرور قوية**:
   ```bash
   sudo -u postgres psql -c "ALTER USER your_db_user WITH PASSWORD 'strong_password';"
   ```

2. **تقييد الوصول حسب IP في ملف `pg_hba.conf`**:
   ```
   # IPv4 local connections:
   host    all             all             127.0.0.1/32            md5
   host    all             all             your_server_ip/32       md5
   ```

3. **تشفير الاتصالات**:
   في ملف `postgresql.conf` قم بتمكين SSL:
   ```
   ssl = on
   ssl_cert_file = '/path/to/server.crt'
   ssl_key_file = '/path/to/server.key'
   ```

4. **إعدادات الجدار الناري**:
   ```bash
   sudo ufw allow from trusted_ip_address to any port 5432
   ```

## 4. النسخ الاحتياطي ومراقبة الأداء

### النسخ الاحتياطي لقاعدة البيانات

1. **نسخ احتياطي يومي**:
   أنشئ سكربت بسيط للنسخ الاحتياطي:

   ```bash
   #!/bin/bash
   # db_backup.sh
   DATE=$(date +"%Y-%m-%d")
   BACKUP_DIR="/path/to/backups"
   
   # تأكد من وجود مجلد النسخ الاحتياطي
   mkdir -p $BACKUP_DIR
   
   # إنشاء نسخة احتياطية
   pg_dump -U your_db_user -h localhost -d your_db_name -F c -f "$BACKUP_DIR/backup-$DATE.dump"
   
   # الاحتفاظ بنسخ آخر 30 يوم فقط
   find $BACKUP_DIR -name "backup-*.dump" -type f -mtime +30 -delete
   ```

   أضف هذا السكربت إلى cron:
   ```
   0 2 * * * /path/to/db_backup.sh
   ```

2. **استعادة النسخة الاحتياطية** (عند الحاجة):
   ```bash
   pg_restore -U your_db_user -h localhost -d your_db_name -c backup-file.dump
   ```

### ترقية قاعدة البيانات لدعم حجم أكبر من المستخدمين

إذا زاد عدد المستخدمين، يجب النظر في الخطوات التالية:

1. **الانتقال من SQLite إلى PostgreSQL**:
   - SQLite مناسب للمواقع الصغيرة (أقل من 100 مستخدم نشط).
   - يُنصح بالترقية إلى PostgreSQL للمواقع المتوسطة والكبيرة.

2. **تقنيات تحسين الأداء**:
   - إضافة فهارس للحقول المستخدمة في البحث والترتيب.
   - تقسيم الجداول الكبيرة (مثل المعاملات).
   - استخدام التخزين المؤقت (Redis) للبيانات المتكررة.

3. **مراقبة أداء قاعدة البيانات**:
   - استخدم أدوات مثل pgBadger لتحليل سجلات الاستعلامات.
   - اضبط الاستعلامات البطيئة وحسّنها.

4. **تحجيم الموارد**:
   - زيادة RAM لخادم قاعدة البيانات (على الأقل 4GB).
   - استخدام خادم منفصل لقاعدة البيانات عند الحاجة.

## 5. تحسينات أمنية إضافية

### تأمين الملفات والمجلدات

- ضبط صلاحيات الملفات بشكل صحيح:
  ```bash
  chmod 750 /path/to/your/app
  chmod 640 config_secrets.py
  ```

### تثبيت وتكوين جدار ناري

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### حماية من هجمات حجب الخدمة (DoS)

في تكوين Nginx:
```nginx
http {
    # تحديد عدد الاتصالات لكل IP
    limit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;
    limit_conn conn_limit_per_ip 10;
    
    # تحديد معدل الطلبات
    limit_req_zone $binary_remote_addr zone=req_limit_per_ip:10m rate=5r/s;
    
    server {
        # ...
        location / {
            limit_req zone=req_limit_per_ip burst=10 nodelay;
            # ...
        }
    }
}
```

### مسح سجلات الأمان

- قم بمراجعة سجلات التطبيق وسجلات الخادم بانتظام.
- استخدم أدوات مثل fail2ban لحظر محاولات الاختراق المتكررة.

## 6. تحديثات الأمان الدورية

- تأكد من تحديث جميع المكتبات والأدوات باستمرار:
  ```bash
  pip install --upgrade pip
  pip install --upgrade -r requirements.txt
  ```

- تحقق من وجود ثغرات أمنية في المكتبات المستخدمة:
  ```bash
  pip install safety
  safety check
  ```

- راقب قنوات إعلانات الأمان لـ Flask وPython والمكتبات الأخرى المستخدمة.

## 7. سياسة الاستجابة للحوادث الأمنية

1. **تحديد فريق الاستجابة**: حدد من سيتعامل مع الحوادث الأمنية.
2. **التوثيق**: احتفظ بسجلات مفصلة لأي حادث أمني.
3. **خطة التواصل**: حدد كيفية إبلاغ المستخدمين بالحوادث الأمنية.
4. **إجراءات العزل والتخفيف**: وثق خطوات احتواء وإصلاح أي اختراق.
5. **التعافي والتحسين**: حدد كيفية استعادة النظام وتحسين الأمان بعد الحوادث.

---

للإبلاغ عن ثغرات أمنية، يرجى التواصل مع فريق الدعم على:
البريد الإلكتروني: `ltsttar00@gmail.com`