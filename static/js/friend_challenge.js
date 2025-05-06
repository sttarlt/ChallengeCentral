/**
 * ملف جافاسكريبت مخصص لصفحة تحدي الصديق
 * يحتوي على وظائف نسخ الرابط ومشاركة واتساب
 */

// تنفيذ الكود عند اكتمال تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    console.log("🔄 تم تحميل ملف friend_challenge.js");
    setupReferralPage();
});

/**
 * تهيئة صفحة الإحالة وإضافة مستمعي الأحداث
 */
function setupReferralPage() {
    // التأكد من وجود عناصر الصفحة قبل إضافة الأحداث
    const copyButton = document.getElementById('copyButton');
    const whatsappButton = document.getElementById('whatsappShareButton');
    const selectTextButton = document.getElementById('selectTextButton');
    const referralField = document.getElementById('referralLink');
    
    // فحص وجود العناصر قبل إضافة المستمعين
    if (referralField) {
        console.log("✅ تم العثور على حقل رابط الإحالة");
        
        // إضافة حدث النقر لتسهيل التحديد
        referralField.addEventListener('click', function() {
            this.select();
            console.log("🔍 تم تحديد النص في حقل الإحالة");
        });
        
        // تعيين خصائص إضافية للحقل
        referralField.setAttribute('readonly', 'readonly');
        referralField.spellcheck = false;
    } else {
        console.error("❌ لم يتم العثور على حقل رابط الإحالة");
    }
    
    // إضافة مستمع حدث لزر النسخ
    if (copyButton) {
        console.log("✅ تم العثور على زر النسخ");
        copyButton.addEventListener('click', function() {
            copyReferralLink();
            console.log("🖱️ تم النقر على زر النسخ");
        });
    } else {
        console.error("❌ لم يتم العثور على زر النسخ");
    }
    
    // إضافة مستمع حدث لزر واتساب
    if (whatsappButton) {
        console.log("✅ تم العثور على زر واتساب");
        whatsappButton.addEventListener('click', function(e) {
            shareViaWhatsApp(e);
            console.log("🖱️ تم النقر على زر واتساب");
        });
    } else {
        console.error("❌ لم يتم العثور على زر واتساب");
    }
    
    // إضافة مستمع حدث لزر تحديد النص
    if (selectTextButton) {
        console.log("✅ تم العثور على زر تحديد النص");
        selectTextButton.addEventListener('click', function() {
            if (referralField) {
                referralField.select();
                console.log("🔍 تم تحديد النص بواسطة الزر");
            }
        });
    }
    
    console.log("✅ تم إعداد صفحة تحدي الصديق");
}

/**
 * نسخ رابط الإحالة إلى الحافظة
 */
function copyReferralLink() {
    // 1. جلب العناصر اللازمة
    const copyButton = document.getElementById('copyButton');
    const copyButtonText = document.getElementById('copyButtonText');
    const copySpinner = document.getElementById('copySpinner');
    const referralField = document.getElementById('referralLink');
    const copyMessage = document.getElementById('copyMessage');
    
    console.log("⚙️ بدء عملية نسخ الرابط");
    
    // التحقق من وجود العناصر
    if (!referralField || !copyButton || !copyButtonText || !copySpinner || !copyMessage) {
        console.error("❌ لم يتم العثور على بعض العناصر المطلوبة للنسخ");
        alert("خطأ في تحميل العناصر اللازمة للنسخ");
        return;
    }
    
    // تغيير حالة زر النسخ ليظهر أنه قيد التنفيذ
    copySpinner.style.display = 'inline-block';
    copyButtonText.textContent = 'جارٍ النسخ...';
    copyButton.disabled = true;
    
    // الحصول على نص الرابط
    const textToCopy = referralField.value.trim();
    if (!textToCopy) {
        console.error("❌ لا يوجد نص للنسخ");
        alert("لا يوجد نص للنسخ!");
        resetCopyUI();
        return;
    }
    
    // تسليط الضوء على حقل النص
    referralField.style.backgroundColor = '#e8f4ff';
    referralField.style.color = '#0d6efd';
    referralField.style.borderColor = '#0d6efd';
    
    console.log("🔄 محاولة نسخ النص: " + textToCopy.substring(0, 30) + "...");
    
    // محاولة النسخ باستخدام Clipboard API
    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
        console.log("🔄 استخدام Clipboard API");
        navigator.clipboard.writeText(textToCopy)
            .then(() => {
                console.log("✅ تم النسخ بنجاح باستخدام Clipboard API");
                showCopySuccess();
            })
            .catch(err => {
                console.error("❌ فشل النسخ باستخدام Clipboard API:", err);
                tryFallbackCopyMethod();
            });
    } else {
        console.log("ℹ️ Clipboard API غير متوفرة، استخدام الطريقة البديلة");
        tryFallbackCopyMethod();
    }
    
    // طريقة النسخ البديلة باستخدام execCommand
    function tryFallbackCopyMethod() {
        try {
            // إنشاء عنصر نصي مؤقت
            const tempTextarea = document.createElement('textarea');
            tempTextarea.value = textToCopy;
            tempTextarea.style.position = 'fixed';
            tempTextarea.style.opacity = '0';
            document.body.appendChild(tempTextarea);
            
            // تحديد النص ومحاولة النسخ
            tempTextarea.focus();
            tempTextarea.select();
            
            const successful = document.execCommand('copy');
            if (successful) {
                console.log("✅ تم النسخ بنجاح باستخدام execCommand");
                showCopySuccess();
            } else {
                console.error("❌ فشل النسخ باستخدام execCommand");
                showManualCopyInstructions();
            }
            
            // إزالة العنصر المؤقت
            document.body.removeChild(tempTextarea);
        } catch (err) {
            console.error("❌ خطأ أثناء محاولة النسخ البديلة:", err);
            showManualCopyInstructions();
        }
    }
    
    // إظهار واجهة النجاح
    function showCopySuccess() {
        // تغيير مظهر الزر
        copyButton.style.backgroundColor = '#198754'; // أخضر
        copyButton.style.borderColor = '#198754';
        copySpinner.style.display = 'none';
        copyButtonText.innerHTML = '<i class="bi bi-check-lg me-1"></i> تم النسخ';
        
        // إظهار رسالة النجاح
        copyMessage.style.display = 'block';
        copyMessage.className = 'alert alert-success my-2 py-2 rounded-3';
        copyMessage.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i> <strong>تم نسخ الرابط بنجاح!</strong>';
        
        // إعادة ضبط واجهة المستخدم بعد فترة
        setTimeout(resetCopyUI, 2000);
    }
    
    // إظهار تعليمات النسخ اليدوي
    function showManualCopyInstructions() {
        // تحديد النص مرة أخرى
        referralField.select();
        
        // تغيير مظهر الزر
        copyButton.style.backgroundColor = '#0dcaf0'; // لون أزرق فاتح
        copyButton.style.borderColor = '#0dcaf0';
        copySpinner.style.display = 'none';
        copyButtonText.innerHTML = '<i class="bi bi-hand-index me-1"></i> انسخ يدوياً';
        
        // إظهار تعليمات النسخ اليدوي
        copyMessage.style.display = 'block';
        copyMessage.className = 'alert alert-info my-2 py-2 rounded-3';
        copyMessage.innerHTML = `
            <i class="bi bi-info-circle-fill me-2"></i>
            <strong>لنسخ الرابط يدوياً:</strong>
            <ol class="mt-2 mb-0">
                <li>النص محدد الآن، اضغط Ctrl+C (ويندوز) أو Cmd+C (ماك) للنسخ</li>
                <li>أو انقر بزر الماوس الأيمن واختر "نسخ"</li>
            </ol>
        `;
        
        // إضافة مراقب لحدث النسخ لاكتشاف النسخ اليدوي
        document.addEventListener('copy', function onCopy() {
            console.log("✅ تم اكتشاف حدث النسخ اليدوي");
            showCopySuccess();
            document.removeEventListener('copy', onCopy);
        }, { once: true });
        
        // إعادة تحديد النص كل ثانية لتسهيل النسخ
        let selectInterval = setInterval(() => {
            referralField.select();
        }, 1000);
        
        // إيقاف التحديد المتكرر بعد 5 ثوان
        setTimeout(() => {
            clearInterval(selectInterval);
            // إعادة ضبط واجهة المستخدم بعد فترة أطول
            setTimeout(resetCopyUI, 5000);
        }, 5000);
    }
    
    // إعادة ضبط واجهة المستخدم
    function resetCopyUI() {
        // إعادة زر النسخ إلى حالته الأصلية
        copyButton.style.backgroundColor = '#0d6efd'; // أزرق
        copyButton.style.borderColor = '#0d6efd';
        copyButton.disabled = false;
        copySpinner.style.display = 'none';
        copyButtonText.innerHTML = '<i class="bi bi-clipboard me-1"></i> نسخ الرابط';
        
        // إخفاء رسالة النسخ تدريجياً
        copyMessage.style.transition = 'opacity 0.5s';
        copyMessage.style.opacity = '0';
        setTimeout(() => {
            copyMessage.style.display = 'none';
            copyMessage.style.opacity = '1';
        }, 500);
        
        // إعادة حقل النص إلى حالته الأصلية
        referralField.style.backgroundColor = '';
        referralField.style.color = '';
        referralField.style.borderColor = '';
    }
}

/**
 * مشاركة الرابط عبر واتساب
 */
function shareViaWhatsApp(event) {
    // منع السلوك الافتراضي للحدث
    if (event) event.preventDefault();
    
    console.log("⚙️ بدء مشاركة رابط واتساب");
    
    // 1. جلب العناصر اللازمة
    const whatsappButton = document.getElementById('whatsappShareButton');
    const referralField = document.getElementById('referralLink');
    const messageElement = document.getElementById('copyMessage');
    
    // التحقق من وجود العناصر
    if (!whatsappButton || !referralField || !messageElement) {
        console.error("❌ لم يتم العثور على بعض العناصر المطلوبة للمشاركة");
        alert("خطأ: لم يتم العثور على عناصر الصفحة المطلوبة");
        return;
    }
    
    // 2. تحديث واجهة المستخدم
    whatsappButton.disabled = true;
    const originalButtonHTML = whatsappButton.innerHTML;
    whatsappButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> جارٍ الفتح...';
    
    // 3. الحصول على رابط الإحالة
    const referralLink = referralField.value.trim();
    if (!referralLink) {
        console.error("❌ لا يوجد رابط للمشاركة");
        // عرض رسالة خطأ
        messageElement.style.display = 'block';
        messageElement.className = 'alert alert-danger my-2 py-2';
        messageElement.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-2"></i> لا يوجد رابط للمشاركة!';
        
        // إعادة الزر إلى حالته الأصلية
        whatsappButton.disabled = false;
        whatsappButton.innerHTML = originalButtonHTML;
        return;
    }
    
    // 4. تجهيز نص المشاركة
    const shareText = `✨ انضم إلى منصة مسابقاتي واحصل على كربتو مجاني! 💰

استخدم رابط الدعوة الخاص بي للحصول على مكافأة ترحيبية:
${referralLink}`;
    
    console.log("🔄 تجهيز نص المشاركة للواتساب");
    
    // 5. تحديد رابط واتساب
    const encodedText = encodeURIComponent(shareText);
    const timestamp = new Date().getTime(); // لتجنب التخزين المؤقت
    const whatsappUrl = `https://wa.me/?text=${encodedText}&t=${timestamp}`;
    
    console.log("🔗 رابط واتساب جاهز");
    
    // 6. محاولة فتح رابط واتساب
    try {
        console.log("🔄 محاولة فتح واتساب");
        
        // إنشاء عنصر رابط مؤقت
        const link = document.createElement('a');
        link.href = whatsappUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        document.body.appendChild(link);
        
        // محاولة النقر على الرابط
        link.click();
        
        console.log("✅ تم النقر على رابط واتساب");
        
        // عرض رسالة نجاح
        messageElement.style.display = 'block';
        messageElement.className = 'alert alert-success my-2 py-2';
        messageElement.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i> تم فتح نافذة المشاركة!';
        
        // تحديث مظهر الزر للإشارة إلى النجاح
        whatsappButton.disabled = false;
        whatsappButton.style.backgroundColor = '#28a745'; // أخضر
        whatsappButton.style.borderColor = '#28a745';
        whatsappButton.innerHTML = '<i class="bi bi-check-circle"></i> <span>تم الفتح</span>';
        
        // إزالة العنصر المؤقت
        setTimeout(() => {
            document.body.removeChild(link);
        }, 100);
        
        // محاولة نسخ النص كاحتياط
        try {
            navigator.clipboard.writeText(shareText);
            console.log("✅ تم نسخ نص المشاركة احتياطياً");
        } catch (clipErr) {
            console.log("⚠️ لم يتم نسخ النص احتياطياً");
        }
    } catch (error) {
        console.error("❌ حدث خطأ أثناء محاولة فتح واتساب:", error);
        
        // إظهار خيار بديل للمستخدم - نسخ النص
        fallbackToClipboard();
    }
    
    // 7. إعادة الزر إلى حالته الأصلية بعد فترة
    setTimeout(() => {
        whatsappButton.style.backgroundColor = '#198754'; // أخضر
        whatsappButton.style.borderColor = '#198754';
        whatsappButton.disabled = false;
        whatsappButton.innerHTML = originalButtonHTML;
        
        // إخفاء رسالة النجاح بعد فترة
        setTimeout(() => {
            messageElement.style.transition = 'opacity 0.5s';
            messageElement.style.opacity = '0';
            setTimeout(() => {
                messageElement.style.display = 'none';
                messageElement.style.opacity = '1';
            }, 500);
        }, 3000);
    }, 3000);
    
    // وظيفة النسخ البديلة
    function fallbackToClipboard() {
        console.log("🔄 الانتقال إلى خيار النسخ البديل");
        
        // تحديد النص للنسخ
        referralField.select();
        
        // محاولة نسخ النص
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(shareText)
                .then(() => {
                    console.log("✅ تم نسخ النص بنجاح");
                    showCopySuccessWithWhatsAppLink();
                })
                .catch(err => {
                    console.error("❌ فشل نسخ النص:", err);
                    showManualWhatsAppInstructions();
                });
        } else {
            // محاولة استخدام الطريقة القديمة
            try {
                const successful = document.execCommand('copy');
                if (successful) {
                    console.log("✅ تم نسخ النص باستخدام execCommand");
                    showCopySuccessWithWhatsAppLink();
                } else {
                    console.warn("⚠️ فشل أمر النسخ");
                    showManualWhatsAppInstructions();
                }
            } catch (err) {
                console.error("❌ خطأ أثناء محاولة النسخ:", err);
                showManualWhatsAppInstructions();
            }
        }
    }
    
    // عرض رسالة نجاح النسخ مع رابط واتساب
    function showCopySuccessWithWhatsAppLink() {
        messageElement.style.display = 'block';
        messageElement.className = 'alert alert-success my-2 py-2';
        messageElement.innerHTML = `
            <i class="bi bi-check-circle-fill me-2"></i> 
            تم نسخ النص! <br>
            <small>الآن افتح واتساب والصق النص للمشاركة</small>
            <div class="mt-2">
                <a href="https://web.whatsapp.com/" target="_blank" class="btn btn-sm btn-success">
                    <i class="bi bi-whatsapp me-1"></i> فتح واتساب ويب
                </a>
            </div>
        `;
        
        // تحديث مظهر الزر
        whatsappButton.disabled = false;
        whatsappButton.style.backgroundColor = '#28a745'; // أخضر
        whatsappButton.style.borderColor = '#28a745';
        whatsappButton.innerHTML = '<i class="bi bi-check-circle"></i> <span>تم النسخ</span>';
    }
    
    // عرض تعليمات واتساب اليدوية
    function showManualWhatsAppInstructions() {
        messageElement.style.display = 'block';
        messageElement.className = 'alert alert-warning my-2 py-2';
        messageElement.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>لم نتمكن من فتح واتساب أو نسخ النص تلقائياً</strong><br>
            <ol class="mt-2 mb-0 small">
                <li>حدد النص في المربع أعلاه</li>
                <li>اضغط Ctrl+C (أو Cmd+C) لنسخه</li>
                <li>افتح واتساب والصق النص</li>
            </ol>
            <div class="mt-2">
                <button onclick="document.getElementById('referralLink').select()" class="btn btn-sm btn-primary me-2">
                    <i class="bi bi-cursor-text"></i> تحديد النص
                </button>
                <a href="https://web.whatsapp.com/" target="_blank" class="btn btn-sm btn-success">
                    <i class="bi bi-whatsapp"></i> فتح واتساب ويب
                </a>
            </div>
        `;
        
        // تحديث مظهر الزر
        whatsappButton.disabled = false;
        whatsappButton.style.backgroundColor = '#ffc107'; // أصفر
        whatsappButton.style.borderColor = '#ffc107';
        whatsappButton.innerHTML = '<i class="bi bi-hand-index"></i> <span>النسخ اليدوي</span>';
    }
}