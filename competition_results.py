# Nueva ruta para mostrar resultados de competencia
@app.route('/competitions/<int:competition_id>/results')
@login_required
def competition_results(competition_id):
    """عرض نتائج المسابقة للمستخدم"""
    competition = Competition.query.get_or_404(competition_id)
    
    # التحقق من أن المستخدم شارك في المسابقة
    participation = Participation.query.filter_by(
        user_id=current_user.id,
        competition_id=competition.id
    ).first_or_404()
    
    # التحقق من أن المستخدم أكمل المسابقة
    if not participation.completed:
        flash('يجب عليك إكمال المسابقة أولاً لرؤية النتائج', 'warning')
        return redirect(url_for('competition_details', competition_id=competition.id))
    
    # الحصول على أسئلة المسابقة
    questions = competition.get_questions()
    
    # تحليل إجابات المستخدم المخزنة
    results = []
    import json
    try:
        if participation.answers_data:
            user_answers = json.loads(participation.answers_data)
            
            for question in questions:
                result_entry = {
                    'question': question,
                    'is_correct': False,
                    'points_earned': 0,
                    'user_answer': None,
                    'user_answer_text': 'لم تتم الإجابة',
                    'correct_answer_text': '',
                }
                
                # التحقق من وجود إجابة لهذا السؤال
                if str(question.id) in user_answers:
                    user_answer = user_answers[str(question.id)]
                    result_entry['user_answer'] = user_answer
                    
                    # الحصول على تفاصيل الإجابة الصحيحة
                    is_correct, points_earned, correct_text = question.check_answer(user_answer)
                    
                    result_entry['is_correct'] = is_correct
                    result_entry['points_earned'] = points_earned
                    result_entry['correct_answer_text'] = correct_text
                    
                    # تحديث نص الإجابة للعرض
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
                
                results.append(result_entry)
    except (json.JSONDecodeError, TypeError) as e:
        app.logger.error(f"خطأ في تحليل بيانات الإجابات: {str(e)}")
        flash('حدث خطأ أثناء تحليل بيانات الإجابات', 'danger')
    
    return render_template(
        'competition_results.html',
        competition=competition,
        participation=participation,
        questions=questions,
        results=results
    )