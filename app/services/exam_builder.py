import random
from app.extensions import db
from app.models import Exam, ExamQuestion, Question, QuestionOption, QuestionMatching, QuestionOrder

QUESTION_TYPES_WITH_OPTIONS = {'multiple_choice', 'single_choice', 'multiple_select', 'true_false', 'video'}
FEEDBACK_MAX_LENGTH = 3000


def user_bank_ids(user_id):
    from app.models import Bank
    return [b.id for b in Bank.query.filter_by(created_by=user_id).all()]


def validate_feedback(feedback):
    if feedback and len(feedback) > FEEDBACK_MAX_LENGTH:
        raise ValueError('La retroalimentación no puede superar 3000 caracteres.')


def validate_points(points):
    try:
        points = float(points)
    except (TypeError, ValueError):
        raise ValueError('Los puntos deben ser numéricos.')
    if points <= 0:
        raise ValueError('Los puntos deben ser mayores que cero.')
    return points


def clear_question_children(question):
    question.options[:] = []
    question.matching_pairs[:] = []
    question.order_items[:] = []


def save_question_payload(question, form):
    qtype = form.get('question_type', question.question_type or 'multiple_choice')
    statement = form.get('statement', '').strip()
    feedback = form.get('feedback_text', '').strip() or None
    if not statement:
        raise ValueError('El enunciado de la pregunta es obligatorio.')
    validate_feedback(feedback)
    question.statement = statement
    question.question_type = qtype
    question.category = form.get('category', 'General').strip() or 'General'
    question.feedback_text = feedback
    question.default_points = validate_points(form.get('default_points', 1))
    question.image_url = form.get('image_url', '').strip() or None
    question.video_url = form.get('video_url', '').strip() or None

    clear_question_children(question)
    if qtype == 'true_false':
        correct = form.get('true_false_correct', 'true')
        question.options.append(QuestionOption(option_text='Verdadero', is_correct=correct == 'true'))
        question.options.append(QuestionOption(option_text='Falso', is_correct=correct == 'false'))
    elif qtype in QUESTION_TYPES_WITH_OPTIONS:
        options = [o.strip() for o in form.getlist('options[]') if o.strip()]
        correct_values = set(form.getlist('correct_options[]') or form.getlist('correct_option'))
        if len(options) < 2:
            raise ValueError('Debes agregar al menos dos opciones.')
        if not correct_values:
            raise ValueError('Debes marcar al menos una respuesta correcta.')
        for idx, text in enumerate(options):
            question.options.append(QuestionOption(option_text=text, is_correct=str(idx) in correct_values))
    elif qtype == 'matching':
        pairs = [(l.strip(), r.strip()) for l, r in zip(form.getlist('left_text[]'), form.getlist('right_text[]')) if l.strip() and r.strip()]
        if not pairs:
            raise ValueError('Debes agregar al menos un par de emparejamiento.')
        for left, right in pairs:
            question.matching_pairs.append(QuestionMatching(left_text=left, right_text=right))
    elif qtype == 'ordering':
        items = [i.strip() for i in form.getlist('order_item[]') if i.strip()]
        if len(items) < 2:
            raise ValueError('Debes agregar al menos dos ítems para ordenar.')
        for idx, item in enumerate(items, start=1):
            question.order_items.append(QuestionOrder(item_text=item, correct_position=idx))
    elif qtype in {'short_answer', 'open_answer'}:
        return question
    else:
        raise ValueError('Tipo de pregunta no soportado.')
    return question


def duplicate_question(question):
    copy = Question(
        bank_id=question.bank_id,
        question_type=question.question_type,
        statement=f'{question.statement} (copia)',
        category=question.category,
        feedback_text=question.feedback_text,
        default_points=question.default_points,
        image_url=question.image_url,
        video_url=question.video_url,
        video_timestamp=question.video_timestamp,
    )
    db.session.add(copy)
    db.session.flush()
    for opt in question.options:
        db.session.add(QuestionOption(question_id=copy.id, option_text=opt.option_text, is_correct=opt.is_correct))
    for pair in question.matching_pairs:
        db.session.add(QuestionMatching(question_id=copy.id, left_text=pair.left_text, right_text=pair.right_text))
    for item in question.order_items:
        db.session.add(QuestionOrder(question_id=copy.id, item_text=item.item_text, correct_position=item.correct_position))
    return copy


def next_order(exam):
    return (max([eq.order_index or 0 for eq in exam.questions] or [0]) + 1)


def add_question_to_exam(exam, question, points=None):
    existing = ExamQuestion.query.get((exam.id, question.id))
    if existing:
        return existing
    eq = ExamQuestion(exam_id=exam.id, question_id=question.id, points=validate_points(points or question.default_points or 1), order_index=next_order(exam))
    db.session.add(eq)
    return eq


def random_questions_for_exam(exam, available_questions, amount):
    amount = int(amount or 0)
    existing_ids = {eq.question_id for eq in exam.questions}
    pool = [q for q in available_questions if q.id not in existing_ids]
    if amount < 1:
        raise ValueError('Indica una cantidad válida de preguntas.')
    if amount > len(pool):
        raise ValueError(f'Solo hay {len(pool)} preguntas disponibles para agregar sin duplicados.')
    return random.sample(pool, amount)
