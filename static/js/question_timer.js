/**
 * إدارة العد التنازلي للوقت في المسابقات
 * يعرض الوقت المتبقي ويقوم بإرسال النموذج تلقائياً عند انتهاء الوقت
 */

class CompetitionTimer {
    /**
     * تهيئة العداد
     * @param {Number} timeLimit الوقت المحدد بالثواني
     * @param {String} timerElementId معرف عنصر عرض الوقت
     * @param {String} formId معرف نموذج الإجابات
     * @param {String} progressBarId معرف شريط التقدم (اختياري)
     */
    constructor(timeLimit, timerElementId, formId, progressBarId = null) {
        this.timeLimit = parseInt(timeLimit);
        this.timeRemaining = this.timeLimit;
        this.timerElement = document.getElementById(timerElementId);
        this.form = document.getElementById(formId);
        this.progressBar = progressBarId ? document.getElementById(progressBarId) : null;
        this.startTime = Date.now();
        this.timerInterval = null;
        this.elapsedTimeInput = document.createElement('input');
        this.elapsedTimeInput.type = 'hidden';
        this.elapsedTimeInput.name = 'elapsed_time';
        this.form.appendChild(this.elapsedTimeInput);
        
        // إضافة حقل للإشارة إلى انتهاء الوقت
        this.timeExpiredInput = document.createElement('input');
        this.timeExpiredInput.type = 'hidden';
        this.timeExpiredInput.name = 'time_expired';
        this.timeExpiredInput.value = '0';
        this.form.appendChild(this.timeExpiredInput);
    }
    
    /**
     * بدء العداد التنازلي
     */
    start() {
        this.startTime = Date.now();
        this.updateTimer();
        this.timerInterval = setInterval(() => this.updateTimer(), 1000);
        console.log(`بدأ العداد التنازلي: ${this.timeLimit} ثانية`);
    }
    
    /**
     * تحديث العداد
     */
    updateTimer() {
        // حساب الوقت المنقضي والوقت المتبقي
        const elapsedTime = Math.floor((Date.now() - this.startTime) / 1000);
        this.timeRemaining = Math.max(0, this.timeLimit - elapsedTime);
        
        // تحديث حقل الوقت المنقضي
        this.elapsedTimeInput.value = elapsedTime;
        
        // تنسيق الوقت
        const minutes = Math.floor(this.timeRemaining / 60);
        const seconds = this.timeRemaining % 60;
        const formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // تحديث عنصر العرض
        if (this.timerElement) {
            this.timerElement.textContent = formattedTime;
            
            // تغيير لون الوقت حسب الوقت المتبقي
            if (this.timeRemaining <= 30) {
                this.timerElement.classList.add('text-danger');
                this.timerElement.classList.add('fw-bold');
                
                // إضافة وميض عند اقتراب نفاد الوقت
                if (this.timeRemaining <= 10) {
                    this.timerElement.classList.add('blink');
                }
            }
        }
        
        // تحديث شريط التقدم
        if (this.progressBar) {
            const percentage = (this.timeRemaining / this.timeLimit) * 100;
            this.progressBar.style.width = `${percentage}%`;
            
            // تغيير لون شريط التقدم حسب الوقت المتبقي
            if (percentage > 60) {
                this.progressBar.classList.remove('bg-warning', 'bg-danger');
                this.progressBar.classList.add('bg-success');
            } else if (percentage > 30) {
                this.progressBar.classList.remove('bg-success', 'bg-danger');
                this.progressBar.classList.add('bg-warning');
            } else {
                this.progressBar.classList.remove('bg-success', 'bg-warning');
                this.progressBar.classList.add('bg-danger');
            }
        }
        
        // إذا انتهى الوقت
        if (this.timeRemaining === 0) {
            this.timeExpired();
        }
    }
    
    /**
     * عند انتهاء الوقت
     */
    timeExpired() {
        clearInterval(this.timerInterval);
        console.log('انتهى الوقت!');
        
        // تعيين حقل انتهاء الوقت
        this.timeExpiredInput.value = '1';
        
        // إظهار رسالة للمستخدم
        const alertElement = document.createElement('div');
        alertElement.className = 'alert alert-danger text-center my-3 fs-4';
        alertElement.innerHTML = '<i class="fas fa-clock me-2"></i> انتهى الوقت! جاري إرسال إجاباتك...';
        this.form.parentNode.insertBefore(alertElement, this.form);
        
        // تعطيل أزرار التحكم
        const submitButtons = this.form.querySelectorAll('button[type="submit"]');
        submitButtons.forEach(button => {
            button.disabled = true;
        });
        
        // إرسال النموذج تلقائياً بعد ثانيتين
        setTimeout(() => {
            this.form.submit();
        }, 2000);
    }
    
    /**
     * إيقاف العداد
     */
    stop() {
        clearInterval(this.timerInterval);
        console.log('تم إيقاف العداد');
    }
}

// المستمع لتحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // البحث عن عنصر وقت المسابقة
    const competitionTimeLimit = document.getElementById('competition-time-limit');
    
    // إذا كانت المسابقة محددة بوقت
    if (competitionTimeLimit) {
        const timeLimit = parseInt(competitionTimeLimit.dataset.timeLimit);
        const timerElementId = 'competition-timer';
        const formId = 'competition-form';
        const progressBarId = 'timer-progress-bar';
        
        // التأكد من وجود العناصر المطلوبة
        if (document.getElementById(timerElementId) && document.getElementById(formId)) {
            // إنشاء وبدء عداد المسابقة
            const timer = new CompetitionTimer(timeLimit, timerElementId, formId, progressBarId);
            timer.start();
            
            // إضافة سلوك التأكيد عند محاولة مغادرة الصفحة
            window.addEventListener('beforeunload', function(e) {
                // إذا كان الوقت لا يزال متبقياً والنموذج لم يرسل بعد
                if (timer.timeRemaining > 0 && !window.isSubmitting) {
                    // إظهار تأكيد للمستخدم
                    e.preventDefault();
                    e.returnValue = 'لديك إجابات غير محفوظة. هل أنت متأكد من أنك تريد المغادرة؟';
                    return e.returnValue;
                }
            });
            
            // تعيين متغير عند إرسال النموذج لمنع ظهور تأكيد المغادرة
            document.getElementById(formId).addEventListener('submit', function() {
                window.isSubmitting = true;
            });
        }
    }
});