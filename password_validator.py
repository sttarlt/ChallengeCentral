"""
أداة للتحقق من قوة كلمات المرور
توفر التحقق من تعقيد كلمات المرور للمشرفين والمستخدمين
"""
import re


def is_strong_password(password, is_admin=False):
    """
    التحقق من قوة كلمة المرور
    
    Args:
        password (str): كلمة المرور للتحقق
        is_admin (bool): هل التحقق لحساب مشرف (متطلبات أكثر صرامة)
    
    Returns:
        tuple: (is_valid, message) - هل كلمة المرور صالحة ورسالة الخطأ إن وجدت
    """
    # المتطلبات الأساسية لجميع المستخدمين
    min_length = 8
    
    # متطلبات إضافية للمشرفين
    if is_admin:
        min_length = 12
    
    # التحقق من الطول الأدنى
    if len(password) < min_length:
        return False, f"كلمة المرور يجب أن تكون {min_length} أحرف على الأقل"
    
    # المتطلبات الأساسية للجميع - حرف كبير واحد على الأقل وحرف صغير واحد على الأقل
    if not re.search(r'[A-Z]', password):
        return False, "كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل"
    
    if not re.search(r'[a-z]', password):
        return False, "كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل"
    
    if not re.search(r'\d', password):
        return False, "كلمة المرور يجب أن تحتوي على رقم واحد على الأقل"
    
    # متطلبات إضافية للمشرفين
    if is_admin:
        # حرف خاص واحد على الأقل
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "كلمة مرور المشرف يجب أن تحتوي على رمز خاص واحد على الأقل مثل !@#$%^&*()"
        
        # تنوع أكبر في الأحرف - على الأقل 3 أحرف كبيرة و3 أرقام
        if len(re.findall(r'[A-Z]', password)) < 2:
            return False, "كلمة مرور المشرف يجب أن تحتوي على حرفين كبيرين على الأقل"
            
        if len(re.findall(r'\d', password)) < 2:
            return False, "كلمة مرور المشرف يجب أن تحتوي على رقمين على الأقل"
    
    # التحقق من عدم استخدام كلمات مرور شائعة
    common_passwords = ['Password123', 'Admin123', 'Abc123456', '12345678', 'qwerty123']
    if password in common_passwords:
        return False, "كلمة المرور شائعة جداً ويسهل تخمينها"
    
    # كلمة المرور قوية بما فيه الكفاية
    return True, ""


def get_password_strength_message(password):
    """
    إنشاء رسالة بمستوى قوة كلمة المرور
    
    Args:
        password (str): كلمة المرور للتقييم
    
    Returns:
        tuple: (strength, message) - قوة كلمة المرور (weak, medium, strong) والرسالة
    """
    # تقييم قوة كلمة المرور
    length_score = min(len(password) / 12, 1.0)  # الطول الأقصى المعتبر هو 12 حرف
    
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    
    char_diversity_score = (has_upper + has_lower + has_digit + has_special) / 4
    
    # حساب النتيجة الإجمالية
    total_score = (length_score + char_diversity_score) / 2
    
    if total_score < 0.5:
        return "weak", "كلمة المرور ضعيفة"
    elif total_score < 0.8:
        return "medium", "كلمة المرور متوسطة القوة"
    else:
        return "strong", "كلمة المرور قوية"