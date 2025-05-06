@app.route('/competitions/<int:competition_id>/submit-answers', methods=['POST'])
@login_required
def submit_answers(competition_id):
    """معالجة تقديم إجابات المسابقة وإضافة النقاط"""
    app.logger.info(f"=== بداية معالجة إجابات المسابقة #{competition_id} للمستخدم {current_user.username} ===")
    
    # متغيرات للتتبع
    competition = None
    participation = None
    total_score = 0
    correct_answers = 0
    total_questions = 0
    bonus_points = 0
    time_bonus = 0
    penalties = 0
    time_expired = 'time_expired' in request.form
    elapsed_time = int(request.form.get('elapsed_time', 0))
    
    # ستخزن نتائج الإجابات لعرضها في صفحة النتائج
    results = []
    
    try:
        # التحقق من وجود المسابقة
        competition = Competition.query.get_or_404(competition_id)
        app.logger.info(f"تم العثور على المسابقة: {competition.title}")
        
        # التحقق من أن المستخدم مشارك بالفعل في المسابقة
        participation = Participation.query.filter_by(
            user_id=current_user.id,
            competition_id=competition.id
        ).first_or_404()
        app.logger.info(f"المستخدم مشارك بالفعل في المسابقة")
        
        # تحديث عدد المحاولات ووقت آخر محاولة
        participation.attempts += 1
        participation.last_attempt_at = datetime.utcnow()
        
        # حفظ وقت إكمال المسابقة (بالثواني)
        if elapsed_time > 0:
            participation.completion_time = elapsed_time
        
        # التحقق من أن المسابقة لا تزال نشطة
        now = datetime.utcnow()
        if not competition.is_active:
            app.logger.warning(f"المسابقة غير نشطة")
            flash('هذه المسابقة غير نشطة ولا يمكن تقديم إجابات', 'warning')
            return redirect(url_for('competition_details', competition_id=competition.id))
            
        if competition.end_date < now:
            app.logger.warning(f"انتهت المسابقة. تاريخ الانتهاء: {competition.end_date}, الآن: {now}")
            flash('لقد انتهت هذه المسابقة ولا يمكن تقديم إجابات', 'warning')
            return redirect(url_for('competition_details', competition_id=competition.id))
        
        # الحصول على جميع أسئلة المسابقة
        questions = competition.get_questions()
        app.logger.info(f"عدد الأسئلة في المسابقة: {len(questions)}")
        total_questions = len(questions)
        
        # إنشاء قاموس لتخزين إجابات المستخدم
        user_answers = {}
        
        # التحقق من كل إجابة
        for question in questions:
            answer_key = f'answer_{question.id}'
            result_entry = {
                'question': question,
                'is_correct': False,
                'points_earned': 0,
                'user_answer': None,
                'user_answer_text': 'لم تتم الإجابة',
                'correct_answer_text': '',
            }
            
            if answer_key in request.form:
                user_answer = request.form[answer_key]
                user_answers[question.id] = user_answer
                result_entry['user_answer'] = user_answer
                app.logger.debug(f"إجابة المستخدم على السؤال {question.id}: {user_answer}")
                
                # استخدام طريقة check_answer من كائن السؤال
                is_correct, points_earned, correct_text = question.check_answer(user_answer)
                
                if is_correct:
                    correct_answers += 1
                    total_score += points_earned
                    result_entry['is_correct'] = True
                    result_entry['points_earned'] = points_earned
                    app.logger.debug(f"إجابة صحيحة! +{points_earned} نقاط")
                else:
                    # تطبيق العقوبة إذا كانت مفعلة
                    if competition.penalty_for_wrong_answers > 0:
                        penalty = competition.penalty_for_wrong_answers
                        penalties += penalty
                        app.logger.debug(f"عقوبة للإجابة الخاطئة: -{penalty} نقطة")
                    
                    app.logger.debug(f"إجابة خاطئة. الإجابة الصحيحة: '{correct_text}'")
                
                # تحديث نص الإجابة للعرض في صفحة النتائج
                if question.question_type in ['multiple_choice', 'image_choice']:
                    try:
                        option_index = int(user_answer)
                        options = question.options_list
                        if 0 <= option_index < len(options):
                            result_entry['user_answer_text'] = options[option_index]
                    except (ValueError, TypeError, IndexError):
                        result_entry['user_answer_text'] = user_answer
                elif question.question_type == 'true_false':
                    result_entry['user_answer_text'] = 'صواب' if user_answer.lower() == 'true' else 'خطأ'
                else:
                    result_entry['user_answer_text'] = user_answer
                
                result_entry['correct_answer_text'] = correct_text
            else:
                app.logger.debug(f"لم يتم العثور على إجابة للسؤال {question.id}")
            
            # إضافة نتيجة هذا السؤال إلى قائمة النتائج
            results.append(result_entry)
        
        # حساب المكافآت الإضافية
        
        # مكافأة الإجابة على جميع الأسئلة بشكل صحيح
        if correct_answers == total_questions and competition.bonus_points > 0:
            bonus_points = competition.bonus_points
            app.logger.info(f"مكافأة الإجابة على جميع الأسئلة بشكل صحيح: +{bonus_points} نقطة")
        
        # حساب مكافأة الوقت (إذا أكمل المسابقة بسرعة)
        if competition.has_time_limit and elapsed_time > 0:
            # إذا كان الوقت المتبقي أكثر من نصف الوقت الإجمالي
            time_remaining_ratio = 1 - (elapsed_time / competition.time_limit)
            if time_remaining_ratio > 0.5:
                time_bonus = int(total_score * 0.2)  # 20% مكافأة للوقت السريع
                app.logger.info(f"مكافأة الوقت السريع: +{time_bonus} نقطة")
        
        app.logger.info(f"النتيجة: {correct_answers} إجابات صحيحة من أصل {total_questions}. المجموع: {total_score} نقطة")
        
        # حفظ إجابات المستخدم كـ JSON
        import json
        participation.answers_data = json.dumps(user_answers)
        
        # تحديث بيانات المشاركة
        participation.score = total_score
        participation.completed = True
        participation.correct_answers = correct_answers
        participation.bonus_points = bonus_points
        participation.penalties = penalties
        participation.time_bonus = time_bonus
        
        # حفظ التغييرات في جدول المشاركة
        db.session.commit()
        app.logger.info(f"تم تحديث بيانات المشاركة")
        
        # إشعار المستخدم بالنتيجة
        flash(f'تم تقديم إجاباتك بنجاح! حصلت على {participation.total_points} نقطة ({correct_answers} من {total_questions} إجابات صحيحة)', 'success')
        
        # إضافة النقاط مباشرة إلى رصيد المستخدم (إلا إذا كان مشرفًا)
        if participation.total_points > 0 and not current_user.is_admin:
            # الاحتفاظ بالنقاط الحالية للمستخدم للمقارنة لاحقًا
            points_before = current_user.points
            
            # إضافة النقاط مباشرة
            current_user.points += participation.total_points
            
            # تسجيل معاملة النقاط
            transaction = PointsTransaction(
                user_id=current_user.id,
                amount=participation.total_points,
                type='competition_reward',
                description=f'مكافأة المسابقة: {competition.title}',
                reference_id=str(competition.id)
            )
            db.session.add(transaction)
            db.session.commit()
            
            app.logger.info(f"تمت إضافة {participation.total_points} نقطة لرصيد المستخدم. الرصيد قبل: {points_before}, الرصيد بعد: {current_user.points}")
        
        # التحقق مما إذا كان المستخدم قد تلقى مكافأة المسابقة من قبل
        has_reward = PointsTransaction.query.filter_by(
            user_id=current_user.id,
            type='competition_bonus',
            reference_id=str(competition.id)
        ).first()
        
        # يتم منح مكافأة المسابقة مرة واحدة فقط
        if not has_reward and not current_user.is_admin:
            # إضافة مكافأة للمسابقة (نقاط إضافية لإكمال المسابقة)
            completion_bonus = competition.points
            
            # إضافة المكافأة
            current_user.points += completion_bonus
            
            # تسجيل معاملة المكافأة
            bonus_transaction = PointsTransaction(
                user_id=current_user.id,
                amount=completion_bonus,
                type='competition_bonus',
                description=f'مكافأة إكمال المسابقة: {competition.title}',
                reference_id=str(competition.id)
            )
            db.session.add(bonus_transaction)
            db.session.commit()
            
            app.logger.info(f"تمت إضافة مكافأة المسابقة: {completion_bonus} نقطة. الرصيد الحالي: {current_user.points}")
            
            # إشعار المستخدم بالمكافأة
            flash(f'حصلت على مكافأة إضافية {completion_bonus} نقطة لإكمال المسابقة!', 'success')
        else:
            app.logger.info(f"المستخدم {current_user.username} تلقى بالفعل مكافأة المسابقة #{competition.id}. لن يتم إضافة مكافأة مرة أخرى.")
        
        app.logger.info(f"=== اكتملت معالجة الإجابات بنجاح. الرصيد الحالي: {current_user.points} ===")
        
        # توجيه المستخدم إلى صفحة النتائج بدلاً من العودة إلى صفحة التفاصيل
        return render_template(
            'competition_results.html',
            competition=competition,
            participation=participation,
            questions=questions,
            results=results
        )
        
    except SQLAlchemyError as e:
        # التراجع عن أي تغييرات في حالة حدوث خطأ
        db.session.rollback()
        app.logger.error(f"خطأ في قاعدة البيانات أثناء معالجة الإجابات: {str(e)}")
        flash('حدث خطأ أثناء معالجة إجاباتك. يرجى المحاولة مرة أخرى.', 'danger')
        
    except Exception as e:
        # التراجع عن أي تغييرات في حالة حدوث خطأ
        db.session.rollback()
        app.logger.error(f"خطأ غير متوقع أثناء معالجة الإجابات: {str(e)}")
        flash('حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.', 'danger')
    
    # في حالة الخطأ، العودة إلى صفحة تفاصيل المسابقة
    return redirect(url_for('competition_details', competition_id=competition_id))