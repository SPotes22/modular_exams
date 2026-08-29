import random
from app.models import ExamSession as DbExamSession, QuestionOption


def normalize_room_code(room_code):
    return str(room_code or '').strip().upper()


def socket_room(room_code):
    return f"session_{normalize_room_code(room_code)}"


def serialize_question(eq, shuffle_options=False):
    q = eq.question
    data = {
        'id': q.id,
        'type': q.question_type,
        'statement': q.statement,
        'points': eq.points,
        'feedback_text': q.feedback_text or '',
        'image_url': q.image_url,
        'video_url': q.video_url,
        'video_timestamp': q.video_timestamp,
    }
    if q.question_type in ['multiple_choice', 'true_false', 'video']:
        opts = list(q.options)
        if shuffle_options:
            random.shuffle(opts)
        data['options'] = [{'id': opt.id, 'text': opt.option_text} for opt in opts]
    elif q.question_type == 'matching':
        pairs = list(q.matching_pairs)
        rights = [p.right_text for p in pairs]
        if shuffle_options:
            random.shuffle(pairs)
            random.shuffle(rights)
        data['pairs'] = [{'id': p.id, 'left_text': p.left_text} for p in pairs]
        data['right_options'] = rights
    elif q.question_type == 'ordering':
        items = list(q.order_items)
        if shuffle_options:
            random.shuffle(items)
        data['order_list'] = [{'id': item.id, 'text': item.item_text} for item in items]
    return data


def load_session_questions(db_session_id):
    db_session = DbExamSession.query.get(db_session_id)
    if not db_session:
        return []
    return [serialize_question(eq) for eq in db_session.exam.questions]


def grade_answer(question, answer):
    answer = answer or {}
    selected_option_text = None
    if question['type'] in ['multiple_choice', 'true_false', 'video']:
        selected_id = answer.get('selected_option_id') or answer.get('selected_id')
        option = QuestionOption.query.get(selected_id) if selected_id else None
        correct = bool(option and option.question_id == question['id'] and option.is_correct)
        if option:
            selected_option_text = option.option_text
    else:
        correct = False
    points = float(question.get('points') or 0) if correct else 0.0
    return {
        'question_id': question['id'],
        'correct': correct,
        'points': points,
        'selected_option_text': selected_option_text,
        'feedback': question.get('feedback_text') or ('Correcta' if correct else 'Incorrecta')
    }


def create_session_question_snapshots(session_obj):
    """
    Crea copias congeladas (snapshots) de las preguntas del examen para la sesión dada.
    Preserva enunciados, opciones, pares, ordenamientos, retroalimentación y puntajes originales.
    """
    from app.extensions import db
    from app.models import SessionQuestionSnapshot

    if not session_obj:
        return []

    existing = SessionQuestionSnapshot.query.filter_by(session_id=session_obj.id).order_by(SessionQuestionSnapshot.order_index).all()
    if existing:
        return existing

    if not session_obj.exam:
        return []

    snapshots = []
    for eq in session_obj.exam.questions:
        q = eq.question
        if not q:
            continue

        opts_data = []
        if q.options:
            for opt in q.options:
                opts_data.append({
                    'id': opt.id,
                    'text': opt.option_text,
                    'option_text': opt.option_text,
                    'is_correct': bool(opt.is_correct)
                })

        match_data = []
        if q.matching_pairs:
            for pair in q.matching_pairs:
                match_data.append({
                    'id': pair.id,
                    'left_text': pair.left_text,
                    'right_text': pair.right_text
                })

        order_data = []
        if q.order_items:
            for item in q.order_items:
                order_data.append({
                    'id': item.id,
                    'item_text': item.item_text,
                    'correct_position': item.correct_position
                })

        snapshot = SessionQuestionSnapshot(
            session_id=session_obj.id,
            original_question_id=q.id,
            order_index=eq.order_index or (len(snapshots) + 1),
            question_type=q.question_type or 'multiple_choice',
            statement=q.statement,
            category=q.category or 'General',
            feedback_text=q.feedback_text,
            points=float(eq.points if eq.points is not None else (q.default_points or 1.0)),
            image_url=q.image_url,
            video_url=q.video_url,
            video_timestamp=q.video_timestamp,
            options_data=opts_data,
            matching_data=match_data,
            ordering_data=order_data
        )
        db.session.add(snapshot)
        snapshots.append(snapshot)

    db.session.commit()
    return snapshots
