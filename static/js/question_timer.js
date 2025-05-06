/**
 * نظام توقيت للأسئلة مع الإغلاق التلقائي عند انتهاء الوقت
 */

class QuestionTimer {
    constructor(options) {
        this.timeLimit = options.timeLimit || 0; // الوقت بالثواني
        this.timerElement = options.timerElement;
        this.submitButton = options.submitButton;
        this.formElement = options.formElement;
        this.onTimeUp = options.onTimeUp || function() {};
        this.timeRemaining = this.timeLimit;
        this.timerInterval = null;
        this.isRunning = false;
        this.hasEnded = false;
    }

    /**
     * بدء العد التنازلي
     */
    start() {
        if (this.timeLimit <= 0 || this.isRunning || this.hasEnded) return;
        
        this.isRunning = true;
        this.timeRemaining = this.timeLimit;
        this.updateDisplay();
        
        this.timerInterval = setInterval(() => {
            this.timeRemaining--;
            this.updateDisplay();
            
            if (this.timeRemaining <= 0) {
                this.end();
            }
        }, 1000);
    }

    /**
     * إيقاف العد التنازلي مؤقتًا
     */
    pause() {
        if (!this.isRunning) return;
        
        clearInterval(this.timerInterval);
        this.isRunning = false;
    }

    /**
     * إنهاء العد التنازلي وتعطيل النموذج
     */
    end() {
        if (this.hasEnded) return;
        
        clearInterval(this.timerInterval);
        this.isRunning = false;
        this.hasEnded = true;
        this.timeRemaining = 0;
        this.updateDisplay();
        
        // تعطيل زر الإرسال
        if (this.submitButton) {
            this.submitButton.disabled = true;
            this.submitButton.classList.add('disabled');
        }
        
        // تعطيل النموذج
        if (this.formElement) {
            const inputs = this.formElement.querySelectorAll('input, select, textarea, button');
            inputs.forEach(input => {
                input.disabled = true;
            });
        }
        
        // عرض رسالة انتهاء الوقت
        const timeUpMessage = document.createElement('div');
        timeUpMessage.className = 'alert alert-danger mt-3 text-center';
        timeUpMessage.innerHTML = '<strong>انتهى الوقت!</strong> لم يعد بإمكانك تقديم إجاباتك.';
        
        if (this.formElement) {
            this.formElement.appendChild(timeUpMessage);
        }
        
        // استدعاء الدالة المخصصة لانتهاء الوقت
        this.onTimeUp();
    }

    /**
     * تحديث عرض الوقت المتبقي
     */
    updateDisplay() {
        if (!this.timerElement) return;
        
        const minutes = Math.floor(this.timeRemaining / 60);
        const seconds = this.timeRemaining % 60;
        
        // تنسيق العرض
        const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        this.timerElement.textContent = timeString;
        
        // تغيير لون المؤقت حسب الوقت المتبقي
        if (this.timeRemaining <= 10) {
            this.timerElement.classList.add('text-danger');
            this.timerElement.classList.add('fw-bold');
        } else if (this.timeRemaining <= 30) {
            this.timerElement.classList.add('text-warning');
            this.timerElement.classList.remove('text-danger');
        } else {
            this.timerElement.classList.remove('text-warning');
            this.timerElement.classList.remove('text-danger');
        }
    }

    /**
     * الحصول على الوقت المتبقي
     */
    getTimeRemaining() {
        return this.timeRemaining;
    }

    /**
     * تحقق مما إذا كان المؤقت ما زال يعمل
     */
    isActive() {
        return this.isRunning;
    }
}

// إضافة دالة لتسجيل وقت البدء والوقت المستغرق للإجابة 
function recordTimingData() {
    const startTime = document.getElementById('start-time');
    if (!startTime) {
        // إنشاء حقل مخفي لتخزين وقت البدء
        const input = document.createElement('input');
        input.type = 'hidden';
        input.id = 'start-time';
        input.name = 'start_time';
        input.value = Date.now().toString();
        document.querySelector('form').appendChild(input);
    }
}

// إضافة دالة حساب الوقت المستغرق عند الإرسال
function calculateElapsedTime() {
    const startTimeField = document.getElementById('start-time');
    if (startTimeField) {
        const startTime = parseInt(startTimeField.value);
        const endTime = Date.now();
        const elapsedSeconds = Math.floor((endTime - startTime) / 1000);
        
        // إنشاء حقل مخفي لإرسال الوقت المستغرق
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'elapsed_time';
        input.value = elapsedSeconds.toString();
        document.querySelector('form').appendChild(input);
    }
}

// تهيئة المؤقت عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // البحث عن عناصر المؤقت في الصفحة
    const timerElement = document.getElementById('question-timer');
    const submitButton = document.querySelector('button[type="submit"]');
    const formElement = document.querySelector('form');
    
    if (timerElement && timerElement.dataset.timeLimit) {
        const timeLimit = parseInt(timerElement.dataset.timeLimit);
        
        // إنشاء كائن المؤقت
        const timer = new QuestionTimer({
            timeLimit: timeLimit,
            timerElement: timerElement,
            submitButton: submitButton,
            formElement: formElement,
            onTimeUp: function() {
                // إرسال النموذج تلقائيًا عند انتهاء الوقت
                if (formElement) {
                    // إضافة حقل مخفي يشير إلى انتهاء الوقت
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'time_expired';
                    input.value = '1';
                    formElement.appendChild(input);
                    
                    // حساب الوقت المستغرق
                    calculateElapsedTime();
                }
            }
        });
        
        // تسجيل وقت البدء
        recordTimingData();
        
        // بدء المؤقت
        timer.start();
        
        // إضافة معالج حدث لزر الإرسال
        if (submitButton && formElement) {
            formElement.addEventListener('submit', function() {
                calculateElapsedTime();
            });
        }
    }
});