import random
import string
from io import BytesIO
import pandas as pd
from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from app.extensions import db, socketio
from app.realtime import events
from app.realtime.manager import session_manager
from app.modes import registry
from app.services.exam_content import normalize_room_code
from app.models import (
    User, Bank, Question, QuestionOption, Exam, ExamQuestion, 
    ExamSession, ExamAttempt, StudentAnswer
)
from app.blueprints.exams import exams_bp

def build_session_results_rows(session_id):
    attempts = ExamAttempt.query.filter_by(session_id=session_id).order_by(ExamAttempt.completed_at.desc()).all()
    rows = []
    for attempt in attempts:
        for answer in attempt.answers:
            correct_option = QuestionOption.query.filter_by(question_id=answer.question_id, is_correct=True).first()
            rows.append({
                'Examen': attempt.session.exam.title,
                'Sala': attempt.session.session_code,
                'Estudiante': attempt.student.username,
                'Nota (%)': attempt.score,
                'Fecha finalización': attempt.completed_at.strftime('%Y-%m-%d %H:%M'),
                'Pregunta': answer.question.statement,
                'Respuesta estudiante': answer.selected_option.option_text if answer.selected_option else 'Respuesta compuesta / sin opción',
                'Respuesta correcta': correct_option.option_text if correct_option else 'Ver rúbrica',
                'Resultado': 'Correcta' if answer.is_correct else 'Incorrecta'
            })
    return rows

def send_rows_as_excel(rows, filename):
    output = BytesIO()
    pd.DataFrame(rows or [{'Mensaje': 'Sin resultados disponibles'}]).to_excel(output, index=False, sheet_name='Resultados')
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@exams_bp.route('/instructor/dashboard')
@login_required
def instructor_dashboard():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))

    exams = Exam.query.filter_by(instructor_id=current_user.id).all()
    sessions = ExamSession.query.join(Exam).filter(Exam.instructor_id == current_user.id).order_by(ExamSession.created_at.desc()).all()
    attempts = ExamAttempt.query.join(ExamSession).join(Exam).filter(Exam.instructor_id == current_user.id).order_by(ExamAttempt.completed_at.desc()).all()
    banks = Bank.query.filter_by(created_by=current_user.id).all()
    
    return render_template('instructor_dashboard.html', 
                         exams=exams, 
                         sessions=sessions, 
                         attempts=attempts,
                         banks=banks)

@exams_bp.route('/instructor/exam/create', methods=['POST'])
@login_required
def create_exam():
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    title = request.form.get('title')
    duration = request.form.get('duration', type=int, default=30)
    
    new_exam = Exam(title=title, duration_minutes=duration, instructor_id=current_user.id)
    db.session.add(new_exam)
    db.session.commit()

    flash(f'Examen "{title}" creado exitosamente.', 'success')
    return redirect(url_for('exams.instructor_dashboard'))

@exams_bp.route('/instructor/session/start/<int:exam_id>', methods=['POST'])
@login_required
def create_session(exam_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    exam = Exam.query.get_or_404(exam_id)
    if exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403

    code = normalize_room_code(''.join(random.choices(string.ascii_uppercase + string.digits, k=6)))
    expected_students = request.form.get('expected_students', type=int, default=0)
    new_session = ExamSession(exam_id=exam_id, session_code=code, status='waiting', expected_students=max(expected_students or 0, 0))
    db.session.add(new_session)
    db.session.commit()
    return redirect(url_for('exams.instructor_lobby', session_id=new_session.id))

@exams_bp.route('/instructor/lobby/<int:session_id>')
@login_required
def instructor_lobby(session_id):
    if current_user.role not in ['instructor', 'superuser', 'admin']:
        return redirect(url_for('auth.home'))

    session_obj = ExamSession.query.get_or_404(session_id)
    attempts = ExamAttempt.query.filter_by(session_id=session_id).order_by(ExamAttempt.completed_at.desc()).all()
    join_url = url_for('auth.student_join_exam', _external=True)
    return render_template('instructor_lobby.html', session=session_obj, attempts=attempts, join_url=join_url)

@exams_bp.route('/exam/presentar/<int:session_id>')
@login_required
def presentar_examen(session_id):
    session_obj = ExamSession.query.get_or_404(session_id)
    exam = session_obj.exam
    
    questions_data = []
    eq_list = list(exam.questions)
    random.shuffle(eq_list)
    
    for eq in eq_list:
        q = eq.question
        
        if q.question_type in ['multiple_choice', 'true_false', 'video']:
            opts = list(q.options)
            random.shuffle(opts)
            questions_data.append({
                'question': q,
                'type': q.question_type,
                'options': opts,
                'points': eq.points
            })
        elif q.question_type == 'matching':
            pairs = list(q.matching_pairs)
            random.shuffle(pairs)
            all_rights = [p.right_text for p in pairs]
            random.shuffle(all_rights)
            questions_data.append({
                'question': q,
                'type': 'matching',
                'pairs': pairs,
                'right_options': all_rights,
                'points': eq.points
            })
        elif q.question_type == 'ordering':
            items = list(q.order_items)
            random.shuffle(items)
            questions_data.append({
                'question': q,
                'type': 'ordering',
                'order_list': items,
                'points': eq.points
            })
    
    return render_template('presentar_examen.html', session=session_obj, exam=exam, questions_data=questions_data)

@exams_bp.route('/instructor/exam/create-advanced', methods=['POST'])
@login_required
def create_advanced_exam():
    if current_user.role != 'instructor':
        return "Acceso denegado", 403
    
    title = request.form.get('title', '').strip()
    duration = request.form.get('duration', type=int, default=30)
    exam_mode = request.form.get('exam_mode', 'instant_feedback')
    bank_id = request.form.get('bank_id', type=int)
    num_questions = request.form.get('num_questions', type=int, default=5)
    
    if not title or not bank_id or not num_questions:
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    bank = Bank.query.get_or_404(bank_id)
    if bank.created_by != current_user.id:
        flash('No tienes permiso para usar este banco.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    # Asegurar la conversión de la relación a lista
    all_questions = list(bank.questions.all()) if hasattr(bank.questions, 'all') else list(bank.questions)
    
    if len(all_questions) < num_questions:
        flash(f'El banco solo tiene {len(all_questions)} preguntas. Selecciona un número menor.', 'warning')
        return redirect(url_for('exams.instructor_dashboard'))
    
    selected_questions = random.sample(all_questions, num_questions)
    
    exam = Exam(
        title=title,
        duration_minutes=duration,
        exam_mode=exam_mode,
        source_bank_id=bank.id,
        random_question_count=num_questions,
        instructor_id=current_user.id
    )
    db.session.add(exam)
    db.session.flush()
    
    for q in selected_questions:
        eq = ExamQuestion(exam_id=exam.id, question_id=q.id, points=1.0)
        db.session.add(eq)
    
    db.session.commit()
    flash(f'Examen "{title}" creado con {num_questions} preguntas aleatorias del banco "{bank.name}".', 'success')
    return redirect(url_for('exams.instructor_dashboard'))


@exams_bp.route('/exam/submit/<int:session_id>', methods=['POST'])
@login_required
def submit_exam(session_id):
    session_obj = ExamSession.query.get_or_404(session_id)
    
    # Evitar múltiples envíos del mismo estudiante para la misma sesión
    attempt_count = ExamAttempt.query.filter_by(student_id=current_user.id, session_id=session_id).count()
    if session_obj.status in ['PAUSED', 'paused']:
        flash('El examen está pausado.', 'warning')
        return redirect(url_for('exams.presentar_examen', session_id=session_id))
    if not session_obj.exam.allow_multiple_attempts and attempt_count >= 1:
        existing_attempt = ExamAttempt.query.filter_by(student_id=current_user.id, session_id=session_id).first()
        flash('Ya has enviado las respuestas para este examen.', 'warning')
        return redirect(url_for('exams.resultados', attempt_id=existing_attempt.id))
    if session_obj.exam.allow_multiple_attempts and attempt_count >= (session_obj.exam.max_attempts or 1):
        flash('Alcanzaste el máximo de intentos permitidos.', 'warning')
        return redirect(url_for('auth.student_join_exam'))

    exam = session_obj.exam
    total_possible = 0.0
    earned = 0.0
    student_answers = []
    
    for eq in exam.questions:
        q = eq.question
        total_possible += eq.points
        
        if q.question_type in ['multiple_choice', 'true_false', 'video']:
            selected_id = request.form.get(f'question_{q.id}', type=int)
            is_correct = False
            if selected_id:
                opt = QuestionOption.query.get(selected_id)
                if opt and opt.is_correct and opt.question_id == q.id:
                    is_correct = True
                    earned += eq.points
            
            student_answers.append({
                'question_id': q.id,
                'selected_option_id': selected_id,
                'is_correct': is_correct
            })
        
        elif q.question_type == 'matching':
            all_correct = True
            for pair in q.matching_pairs:
                selected_right = request.form.get(f'question_{q.id}_pair_{pair.id}')
                if selected_right != pair.right_text:
                    all_correct = False
            if all_correct:
                earned += eq.points
            student_answers.append({
                'question_id': q.id,
                'selected_option_id': None,
                'is_correct': all_correct
            })
        
        elif q.question_type == 'ordering':
            order_map = {}
            for item in q.order_items:
                pos = request.form.get(f'order_{q.id}_{item.id}', type=int)
                if pos is not None:
                    order_map[item.id] = pos
            
            all_correct = True
            for item in q.order_items:
                if order_map.get(item.id) != item.correct_position:
                    all_correct = False
                    break
            if all_correct:
                earned += eq.points
            student_answers.append({
                'question_id': q.id,
                'selected_option_id': None,
                'is_correct': all_correct
            })
    
    final_score = (earned / total_possible * 100.0) if total_possible > 0 else 0.0
    
    attempt = ExamAttempt(
        student_id=current_user.id,
        session_id=session_id,
        score=round(final_score, 2),
        status='completed',
        attempt_number=attempt_count + 1,
        earned_points=round(earned, 2),
        max_points=round(total_possible, 2)
    )
    db.session.add(attempt)
    db.session.flush()
    
    for ans_data in student_answers:
        sa = StudentAnswer(
            attempt_id=attempt.id,
            question_id=ans_data['question_id'],
            selected_option_id=ans_data.get('selected_option_id'),
            is_correct=ans_data['is_correct'],
            points_awarded=0.0
        )
        db.session.add(sa)
    
    db.session.commit()

    room_name = f"session_{session_obj.session_code}"
    completed_count = ExamAttempt.query.filter_by(session_id=session_id, status='completed').count()
    
    if session_obj.expected_students and completed_count >= session_obj.expected_students:
        session_obj.status = 'finished'
        db.session.commit()
        socketio.emit('all_students_finished', {
            'session_id': session_id,
            'download_url': url_for('exams.download_session_results_excel', session_id=session_id)
        }, to=room_name)
    
    socketio.emit('student_finished', {
        'student_id': current_user.id,
        'username': current_user.username,
        'session_id': session_id
    }, to=room_name)
    
    flash('Examen enviado con éxito.', 'success')
    return redirect(url_for('exams.resultados', attempt_id=attempt.id))

@exams_bp.route('/resultados/<int:attempt_id>')
@login_required
def resultados(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    answers = StudentAnswer.query.filter_by(attempt_id=attempt.id).all()
    return render_template('resultados.html', attempt=attempt, answers=answers)

@exams_bp.route('/exam/close/<int:session_id>', methods=['POST'])
@login_required
def close_session(session_id):
    session_obj = ExamSession.query.get_or_404(session_id)
    if current_user.role == 'instructor':
        session_obj.status = 'finished'
        db.session.commit()
        
        socketio.emit('exam_closed', {'session_id': session_id}, room=f"session_{session_obj.session_code}")
        flash('La sesión de examen ha sido finalizada correctamente.', 'info')
    
    return redirect(url_for('exams.instructor_dashboard'))

@exams_bp.route('/instructor/reports')
@login_required
def exam_reports():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    sessions = ExamSession.query.join(Exam).filter(
        Exam.instructor_id == current_user.id,
        ExamSession.status == 'finished'
    ).order_by(ExamSession.created_at.desc()).all()
    return render_template('exam_reports.html', sessions=sessions)

@exams_bp.route('/instructor/session/<int:session_id>/report')
@login_required
def session_report(session_id):
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    session_obj = ExamSession.query.get_or_404(session_id)
    if session_obj.exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    attempts = ExamAttempt.query.filter_by(session_id=session_id).order_by(ExamAttempt.completed_at.desc()).all()
    return render_template('session_report.html', session=session_obj, attempts=attempts)

@exams_bp.route('/instructor/session/<int:session_id>/results.xlsx')
@login_required
def download_session_results_excel(session_id):
    if current_user.role != 'instructor':
        return 'Acceso denegado', 403
    session_obj = ExamSession.query.get_or_404(session_id)
    if session_obj.exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    return send_rows_as_excel(build_session_results_rows(session_id), f'resultados_{session_obj.session_code}.xlsx')

@exams_bp.route('/instructor/attempt/<int:attempt_id>/results.xlsx')
@login_required
def download_attempt_results_excel(attempt_id):
    if current_user.role != 'instructor':
        return 'Acceso denegado', 403
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    if attempt.session.exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    rows = [row for row in build_session_results_rows(attempt.session_id) if row['Estudiante'] == attempt.student.username]
    return send_rows_as_excel(rows, f'resultado_{attempt.student.username}_{attempt.session.session_code}.xlsx')


@exams_bp.route('/session/status/<int:session_id>')
@login_required
def get_session_status_json(session_id):
    session_obj = ExamSession.query.get_or_404(session_id)

    # Obtener los intentos/estudiantes conectados a esta sesión
    attempts = ExamAttempt.query.filter_by(session_id=session_id).all()
    students = [a.student.username for a in attempts if a.student]

    return {
        'status': session_obj.status,
        'session_id': session_obj.id,
        'session_code': session_obj.session_code,
        'students': list(set(students))
    }

@exams_bp.route('/instructor/session/start-ajax/<int:session_id>', methods=['POST'])
@login_required
def start_session_ajax(session_id):
    if current_user.role != 'instructor':
        return {'error': 'Acceso denegado'}, 403

    session_obj = ExamSession.query.get_or_404(session_id)
    if session_obj.exam.instructor_id != current_user.id:
        return {'error': 'Acceso denegado'}, 403

    session_obj.status = 'RUNNING'
    db.session.commit()
    realtime_session = session_manager.get_or_create_by_db_session(session_obj)
    realtime_session.status = 'RUNNING'
    registry.get(realtime_session.mode, socketio, session_manager).on_start(realtime_session)

    return {'success': True, 'status': session_obj.status}

@exams_bp.route('/instructor/exams')
@login_required
def library():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    from app.models import ExamClass, ExamGroup
    exams = Exam.query.filter_by(instructor_id=current_user.id).order_by(Exam.updated_at.desc().nullslast(), Exam.id.desc()).all()
    classes = ExamClass.query.filter_by(instructor_id=current_user.id).order_by(ExamClass.name).all()
    groups = ExamGroup.query.filter_by(instructor_id=current_user.id).order_by(ExamGroup.name).all()
    return render_template('exam_library.html', exams=exams, classes=classes, groups=groups)

@exams_bp.route('/instructor/exam/new', methods=['GET', 'POST'])
@login_required
def new_exam_builder():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El nombre del examen es obligatorio.', 'danger')
            return redirect(url_for('exams.new_exam_builder'))
        exam = Exam(title=title, instructor_id=current_user.id, duration_minutes=request.form.get('duration', type=int, default=30))
        db.session.add(exam)
        db.session.commit()
        return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))
    return render_template('exam_builder.html', exam=None, banks=Bank.query.filter_by(created_by=current_user.id).all(), all_questions=[])

@exams_bp.route('/instructor/exam/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exam_builder(exam_id):
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    exam = Exam.query.get_or_404(exam_id)
    if exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El nombre del examen es obligatorio.', 'danger')
            return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))
        exam.title = title
        exam.instructions = request.form.get('instructions', '').strip() or None
        exam.duration_minutes = request.form.get('duration_minutes', type=int, default=30)
        exam.exam_mode = request.form.get('exam_mode', 'instant_feedback')
        exam.allow_multiple_attempts = bool(request.form.get('allow_multiple_attempts'))
        exam.max_attempts = max(request.form.get('max_attempts', type=int, default=1), 1)
        for eq in exam.questions:
            eq.points = max(request.form.get(f'points_{eq.question_id}', type=float, default=eq.points), 0.1)
        db.session.commit()
        flash('Cambios del examen guardados.', 'success')
        return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))
    banks = Bank.query.filter_by(created_by=current_user.id).all()
    bank_ids = [b.id for b in banks]
    all_questions = Question.query.filter(Question.bank_id.in_(bank_ids)).order_by(Question.updated_at.desc().nullslast(), Question.id.desc()).all() if bank_ids else []
    return render_template('exam_builder.html', exam=exam, banks=banks, all_questions=all_questions)

@exams_bp.route('/instructor/exam/<int:exam_id>/add-bank', methods=['POST'])
@login_required
def add_bank_questions(exam_id):
    from app.services.exam_builder import add_question_to_exam, random_questions_for_exam
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    bank_ids = [b.id for b in Bank.query.filter_by(created_by=current_user.id).all()]
    selected_ids = [int(x) for x in request.form.getlist('question_ids')]
    if request.form.get('random_count'):
        available = Question.query.filter(Question.bank_id.in_(bank_ids)).all()
        try:
            selected = random_questions_for_exam(exam, available, request.form.get('random_count', type=int))
            selected_ids = [q.id for q in selected]
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))
    for q in Question.query.filter(Question.id.in_(selected_ids), Question.bank_id.in_(bank_ids)).all():
        add_question_to_exam(exam, q)
    db.session.commit()
    flash('Preguntas agregadas al examen.', 'success')
    return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))

@exams_bp.route('/instructor/exam/<int:exam_id>/question/create', methods=['POST'])
@login_required
def create_question_inside_exam(exam_id):
    from app.services.exam_builder import add_question_to_exam, save_question_payload
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    bank_id = request.form.get('bank_id', type=int)
    bank = Bank.query.get_or_404(bank_id) if bank_id else None
    if not bank or bank.created_by != current_user.id:
        flash('Selecciona un banco propio para guardar la pregunta.', 'danger')
        return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))
    q = Question(bank_id=bank.id, statement='Temporal')
    db.session.add(q)
    try:
        save_question_payload(q, request.form)
        db.session.flush()
        add_question_to_exam(exam, q, q.default_points)
        db.session.commit()
        flash('Pregunta creada y agregada al examen.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))

@exams_bp.route('/instructor/exam/<int:exam_id>/question/<int:question_id>/<action>', methods=['POST'])
@login_required
def exam_question_action(exam_id, question_id, action):
    from app.services.exam_builder import duplicate_question, add_question_to_exam
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    eq = ExamQuestion.query.get_or_404((exam_id, question_id))
    if action == 'remove':
        db.session.delete(eq)
    elif action == 'duplicate':
        qcopy = duplicate_question(eq.question)
        db.session.flush()
        add_question_to_exam(exam, qcopy, eq.points)
    elif action in {'up', 'down'}:
        ordered = list(exam.questions)
        idx = ordered.index(eq)
        swap_idx = idx - 1 if action == 'up' else idx + 1
        if 0 <= swap_idx < len(ordered):
            ordered[idx].order_index, ordered[swap_idx].order_index = ordered[swap_idx].order_index, ordered[idx].order_index
    else:
        return 'Acción no soportada', 400
    db.session.commit()
    return redirect(url_for('exams.edit_exam_builder', exam_id=exam.id))

@exams_bp.route('/instructor/exam/<int:exam_id>/duplicate', methods=['POST'])
@login_required
def duplicate_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    copy = Exam(title=f'{exam.title} (copia)', instructions=exam.instructions, duration_minutes=exam.duration_minutes, passing_score=exam.passing_score, exam_mode=exam.exam_mode, instructor_id=current_user.id, allow_multiple_attempts=exam.allow_multiple_attempts, max_attempts=exam.max_attempts)
    db.session.add(copy); db.session.flush()
    for eq in exam.questions:
        db.session.add(ExamQuestion(exam_id=copy.id, question_id=eq.question_id, points=eq.points, order_index=eq.order_index))
    db.session.commit()
    flash('Examen duplicado.', 'success')
    return redirect(url_for('exams.library'))

@exams_bp.route('/instructor/exam/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    db.session.delete(exam); db.session.commit(); flash('Examen eliminado.', 'info')
    return redirect(url_for('exams.library'))

@exams_bp.route('/instructor/session/configure/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def configure_session(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    if request.method == 'POST':
        code = normalize_room_code(''.join(random.choices(string.ascii_uppercase + string.digits, k=6)))
        session = ExamSession(exam_id=exam.id, session_code=code, status='READY', expected_students=request.form.get('expected_students', type=int, default=0), question_order=request.form.get('question_order', 'original'))
        db.session.add(session); db.session.commit()
        return redirect(url_for('exams.instructor_lobby', session_id=session.id))
    return render_template('session_config.html', exam=exam)

@exams_bp.route('/instructor/session/<int:session_id>/<action>', methods=['POST'])
@login_required
def control_session(session_id, action):
    allowed = {'pause': 'PAUSED', 'resume': 'RUNNING', 'finish': 'FINISHED', 'start': 'RUNNING'}
    session = ExamSession.query.get_or_404(session_id)
    if current_user.role != 'instructor' or session.exam.instructor_id != current_user.id or action not in allowed:
        return 'Acceso denegado', 403
    session.status = allowed[action]
    db.session.commit()
    event = {'pause': 'exam_paused', 'resume': 'exam_resumed', 'finish': 'exam_finished', 'start': 'exam_started'}[action]
    socketio.emit(event, {'session_id': session.id, 'status': session.status}, to=f"session_{session.session_code}")
    flash(f'Sesión actualizada: {session.status}', 'success')
    return redirect(url_for('exams.instructor_lobby', session_id=session.id))

@exams_bp.route('/instructor/classes', methods=['GET', 'POST'])
@login_required
def classes():
    from app.models import ExamClass
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    if request.method == 'POST':
        cls = ExamClass(name=request.form.get('name', '').strip(), subject=request.form.get('subject', '').strip(), description=request.form.get('description', '').strip(), instructor_id=current_user.id)
        if not cls.name:
            flash('El nombre de la clase es obligatorio.', 'danger')
        else:
            db.session.add(cls); db.session.commit(); flash('Clase creada.', 'success')
    return render_template('exam_classes.html', classes=ExamClass.query.filter_by(instructor_id=current_user.id).all(), exams=Exam.query.filter_by(instructor_id=current_user.id).all())

@exams_bp.route('/instructor/class/<int:class_id>/assign', methods=['POST'])
@login_required
def assign_exam_class(class_id):
    from app.models import ExamClass
    cls = ExamClass.query.get_or_404(class_id)
    exam = Exam.query.get_or_404(request.form.get('exam_id', type=int))
    if current_user.role != 'instructor' or cls.instructor_id != current_user.id or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    if exam not in cls.exams:
        cls.exams.append(exam)
    db.session.commit(); flash('Examen asignado a la clase.', 'success')
    return redirect(url_for('exams.classes'))

@exams_bp.route('/instructor/history')
@login_required
def history():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    sessions = ExamSession.query.join(Exam).filter(Exam.instructor_id == current_user.id).order_by(ExamSession.created_at.desc()).all()
    return render_template('exam_history.html', sessions=sessions)

@exams_bp.route('/instructor/results')
@login_required
def results_overview():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    subject = request.args.get('subject', '')
    attempts = ExamAttempt.query.join(ExamSession).join(Exam).filter(Exam.instructor_id == current_user.id).order_by(ExamAttempt.completed_at.desc()).all()
    if subject:
        attempts = [a for a in attempts if any(c.subject == subject for c in a.session.exam.classes)]
    subjects = sorted({c.subject for e in Exam.query.filter_by(instructor_id=current_user.id).all() for c in e.classes if c.subject})
    return render_template('exam_results_overview.html', attempts=attempts, subjects=subjects, subject=subject)

@exams_bp.route('/instructor/exam/<int:exam_id>/export/<answers>')
@login_required
def export_exam_document(exam_id, answers):
    exam = Exam.query.get_or_404(exam_id)
    if current_user.role != 'instructor' or exam.instructor_id != current_user.id:
        return 'Acceso denegado', 403
    return render_template('exam_export.html', exam=exam, include_answers=(answers == 'with-answers'))

@exams_bp.route('/instructor/preferences', methods=['POST'])
@login_required
def update_preferences():
    if current_user.role != 'instructor':
        return 'Acceso denegado', 403
    current_user.default_exam_view = request.form.get('default_exam_view', 'questions')
    db.session.commit(); flash('Preferencia guardada.', 'success')
    return redirect(url_for('exams.instructor_dashboard'))
