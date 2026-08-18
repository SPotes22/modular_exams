import pandas as pd
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Bank, Question, QuestionOption, QuestionMatching, QuestionOrder
from app.blueprints.questions import questions_bp
from app.services.exam_builder import duplicate_question, save_question_payload, validate_feedback

@questions_bp.route('/instructor/bank/create', methods=['POST'])
@login_required
def create_bank():
    if current_user.role != 'instructor':
        return "Acceso denegado", 403
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('El nombre del banco es obligatorio.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    existing = Bank.query.filter_by(name=name, created_by=current_user.id).first()
    if existing:
        flash('Ya existe un banco con ese nombre.', 'warning')
        return redirect(url_for('exams.instructor_dashboard'))
    
    bank = Bank(name=name, description=description, created_by=current_user.id)
    db.session.add(bank)
    db.session.commit()
    flash(f'Banco "{name}" creado exitosamente.', 'success')
    return redirect(url_for('exams.instructor_dashboard'))

@questions_bp.route('/instructor/bank/delete/<int:bank_id>', methods=['POST'])
@login_required
def delete_bank(bank_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403
    
    bank = Bank.query.get_or_404(bank_id)
    if bank.created_by != current_user.id:
        flash('No tienes permiso para eliminar este banco.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    db.session.delete(bank)
    db.session.commit()
    flash(f'Banco "{bank.name}" eliminado.', 'info')
    return redirect(url_for('exams.instructor_dashboard'))

@questions_bp.route('/instructor/question/create', methods=['POST'])
@login_required
def create_advanced_question():
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    bank_id = request.form.get('bank_id', type=int)
    bank = Bank.query.get_or_404(bank_id) if bank_id else None
    if not bank or bank.created_by != current_user.id:
        flash('Debes seleccionar un banco propio.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    question = Question(bank_id=bank.id, statement='Temporal')
    db.session.add(question)
    try:
        save_question_payload(question, request.form)
        db.session.commit()
        flash('Pregunta creada exitosamente.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')

    next_url = request.form.get('next')
    return redirect(next_url or url_for('questions.mis_preguntas'))

@questions_bp.route('/instructor/mis-preguntas')
@login_required
def mis_preguntas():
    if current_user.role != 'instructor':
        return redirect(url_for('auth.home'))
    
    banks = Bank.query.filter_by(created_by=current_user.id).all()
    bank_ids = [b.id for b in banks]
    questions = Question.query.filter(Question.bank_id.in_(bank_ids)).all()
    
    filter_type = request.args.get('type', '')
    filter_bank = request.args.get('bank', type=int)
    search = request.args.get('q', '').strip().lower()
    
    if filter_type:
        questions = [q for q in questions if q.question_type == filter_type]
    if filter_bank:
        questions = [q for q in questions if q.bank_id == filter_bank]
    if search:
        questions = [q for q in questions if search in q.statement.lower() or search in (q.category or '').lower()]
    
    return render_template(
        'mis_preguntas.html',
        banks=banks,
        questions=questions,
        filter_type=filter_type,
        filter_bank=filter_bank,
        search=search
    )

@questions_bp.route('/instructor/question/delete/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403
    
    question = Question.query.get_or_404(question_id)
    if question.bank.created_by != current_user.id:
        flash('No tienes permiso para eliminar esta pregunta.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))
    
    db.session.delete(question)
    db.session.commit()
    flash('Pregunta eliminada.', 'info')
    return redirect(url_for('questions.mis_preguntas'))

@questions_bp.route('/instructor/question/import-excel', methods=['POST'])
@login_required
def import_questions_excel():
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    bank_id = request.form.get('bank_id', type=int)
    if not bank_id:
        flash('Debes seleccionar un banco de preguntas.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    bank = Bank.query.get_or_404(bank_id)
    if bank.created_by != current_user.id:
        flash('No tienes permiso para modificar este banco.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    if 'excel_file' not in request.files:
        flash('No se subió ningún archivo.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    file = request.files['excel_file']
    if file.filename == '':
        flash('No se seleccionó ningún archivo.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    try:
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file)
        else:
            flash('Formato no soportado. Debe ser un archivo .xlsx, .xls o .csv', 'danger')
            return redirect(url_for('questions.mis_preguntas'))

        imported_count = 0

        for _, row in df.iterrows():
            statement = str(row.get('statement', '')).strip()
            if not statement or pd.isna(row.get('statement')):
                continue

            q_type = str(row.get('question_type', 'multiple_choice')).strip().lower()
            category = str(row.get('category', 'General')).strip()
            feedback = str(row.get('feedback_text', '')).strip() if pd.notna(row.get('feedback_text')) else None
            image_url = str(row.get('image_url', '')).strip() if pd.notna(row.get('image_url')) else None
            video_url = str(row.get('video_url', '')).strip() if pd.notna(row.get('video_url')) else None

            question = Question(
                bank_id=bank.id,
                question_type=q_type,
                statement=statement,
                category=category,
                feedback_text=feedback,
                image_url=image_url,
                video_url=video_url
            )
            db.session.add(question)
            db.session.flush()

            if q_type in ['multiple_choice', 'true_false', 'video']:
                options_str = str(row.get('options', ''))
                correct_idx = int(row.get('correct_option', 0)) if pd.notna(row.get('correct_option')) else 0
                
                if pd.notna(options_str) and options_str:
                    options_list = [opt.strip() for opt in options_str.split('|') if opt.strip()]
                    for idx, opt_text in enumerate(options_list):
                        opt = QuestionOption(
                            question_id=question.id,
                            option_text=opt_text,
                            is_correct=(idx == correct_idx)
                        )
                        db.session.add(opt)

            elif q_type == 'matching':
                pairs_str = str(row.get('pairs', ''))
                if pd.notna(pairs_str) and pairs_str:
                    pair_items = pairs_str.split('|')
                    for p in pair_items:
                        if ':' in p:
                            left, right = p.split(':', 1)
                            pair = QuestionMatching(
                                question_id=question.id,
                                left_text=left.strip(),
                                right_text=right.strip()
                            )
                            db.session.add(pair)

            elif q_type == 'ordering':
                order_str = str(row.get('items', ''))
                if pd.notna(order_str) and order_str:
                    items = [it.strip() for it in order_str.split('|') if it.strip()]
                    for idx, item_text in enumerate(items, start=1):
                        order_item = QuestionOrder(
                            question_id=question.id,
                            item_text=item_text,
                            correct_position=idx
                        )
                        db.session.add(order_item)

            imported_count += 1

        db.session.commit()
        flash(f'¡Se importaron {imported_count} preguntas exitosamente desde el Excel!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el archivo Excel: {str(e)}', 'danger')

    return redirect(url_for('questions.mis_preguntas'))

@questions_bp.route('/instructor/bank/edit/<int:bank_id>', methods=['POST'])
@login_required
def edit_bank(bank_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    bank = Bank.query.get_or_404(bank_id)
    if bank.created_by != current_user.id:
        flash('No tienes permiso para editar este banco.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('El nombre del banco no puede estar vacío.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    bank.name = name
    bank.description = description
    db.session.commit()
    flash('Banco actualizado exitosamente.', 'success')
    return redirect(url_for('questions.mis_preguntas'))


@questions_bp.route('/instructor/question/edit/<int:question_id>', methods=['POST'])
@login_required
def edit_question(question_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403

    question = Question.query.get_or_404(question_id)
    if question.bank.created_by != current_user.id:
        flash('No tienes permiso para modificar esta pregunta.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    try:
        save_question_payload(question, request.form)
        db.session.commit()
        flash('Pregunta actualizada correctamente.', 'success')
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), 'danger')

    return redirect(request.form.get('next') or url_for('questions.mis_preguntas'))


@questions_bp.route('/instructor/question/duplicate/<int:question_id>', methods=['POST'])
@login_required
def duplicate_question_route(question_id):
    if current_user.role != 'instructor':
        return "Acceso denegado", 403
    question = Question.query.get_or_404(question_id)
    if question.bank.created_by != current_user.id:
        flash('No tienes permiso para duplicar esta pregunta.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))
    duplicate_question(question)
    db.session.commit()
    flash('Pregunta duplicada correctamente.', 'success')
    return redirect(url_for('questions.mis_preguntas'))
