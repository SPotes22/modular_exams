import pandas as pd
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Bank, Question, QuestionOption, QuestionMatching, QuestionOrder
from app.blueprints.questions import questions_bp

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
    
    question_type = request.form.get('question_type', 'multiple_choice')
    bank_id = request.form.get('bank_id', type=int)
    statement = request.form.get('statement', '').strip()
    category = request.form.get('category', 'General')
    feedback_text = request.form.get('feedback_text', '').strip() or None
    image_url = request.form.get('image_url', '').strip() or None
    video_url = request.form.get('video_url', '').strip() or None
    
    if not bank_id:
        flash('Debes seleccionar un banco.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    bank = Bank.query.get_or_404(bank_id)
    if bank.created_by != current_user.id:
        flash('No tienes permiso para agregar preguntas a este banco.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    if not statement:
        flash('El enunciado de la pregunta es obligatorio.', 'danger')
        return redirect(url_for('exams.instructor_dashboard'))
    
    question = Question(
        bank_id=bank_id,
        question_type=question_type,
        statement=statement,
        category=category,
        feedback_text=feedback_text,
        image_url=image_url,
        video_url=video_url
    )
    db.session.add(question)
    db.session.flush()
    
    if question_type in ['multiple_choice', 'true_false', 'video']:
        options_texts = request.form.getlist('options[]')
        correct_idx = request.form.get('correct_option', type=int, default=0)
        
        if not options_texts or not any(opt.strip() for opt in options_texts):
            flash('Debes agregar al menos una opción.', 'danger')
            db.session.rollback()
            return redirect(url_for('exams.instructor_dashboard'))
        
        for idx, opt_text in enumerate(options_texts):
            if opt_text.strip():
                opt = QuestionOption(
                    question_id=question.id,
                    option_text=opt_text.strip(),
                    is_correct=(idx == correct_idx)
                )
                db.session.add(opt)
    
    elif question_type == 'matching':
        left_texts = request.form.getlist('left_text[]')
        right_texts = request.form.getlist('right_text[]')
        
        if not left_texts or not any(l.strip() for l in left_texts):
            flash('Debes agregar al menos un par de emparejamiento.', 'danger')
            db.session.rollback()
            return redirect(url_for('exams.instructor_dashboard'))
        
        for left, right in zip(left_texts, right_texts):
            if left.strip() and right.strip():
                pair = QuestionMatching(
                    question_id=question.id,
                    left_text=left.strip(),
                    right_text=right.strip()
                )
                db.session.add(pair)
    
    elif question_type == 'ordering':
        order_items = request.form.getlist('order_item[]')
        
        if not order_items or not any(item.strip() for item in order_items):
            flash('Debes agregar al menos un ítem para ordenar.', 'danger')
            db.session.rollback()
            return redirect(url_for('exams.instructor_dashboard'))
        
        for idx, item in enumerate(order_items):
            if item.strip():
                order = QuestionOrder(
                    question_id=question.id,
                    item_text=item.strip(),
                    correct_position=idx + 1
                )
                db.session.add(order)
    
    db.session.commit()
    flash('Pregunta creada exitosamente.', 'success')
    return redirect(url_for('exams.instructor_dashboard'))

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
    
    if filter_type:
        questions = [q for q in questions if q.question_type == filter_type]
    if filter_bank:
        questions = [q for q in questions if q.bank_id == filter_bank]
    
    return render_template(
        'mis_preguntas.html',
        banks=banks,
        questions=questions,
        filter_type=filter_type,
        filter_bank=filter_bank
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

    statement = request.form.get('statement', '').strip()
    category = request.form.get('category', 'General').strip()
    feedback_text = request.form.get('feedback_text', '').strip() or None

    if not statement:
        flash('El enunciado es obligatorio.', 'danger')
        return redirect(url_for('questions.mis_preguntas'))

    question.statement = statement
    question.category = category
    question.feedback_text = feedback_text

    db.session.commit()
    flash('Pregunta actualizada correctamente.', 'success')
    return redirect(url_for('questions.mis_preguntas'))
