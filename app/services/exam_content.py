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
    if question['type'] in ['multiple_choice', 'true_false', 'video']:
        selected_id = answer.get('selected_option_id') or answer.get('selected_id')
        option = QuestionOption.query.get(selected_id) if selected_id else None
        correct = bool(option and option.question_id == question['id'] and option.is_correct)
    else:
        # Complex question types still persist progress in realtime; final HTTP submit remains canonical.
        correct = False
    points = float(question.get('points') or 0) if correct else 0.0
    return {
        'question_id': question['id'],
        'correct': correct,
        'points': points,
        'feedback': question.get('feedback_text') or ('Correcta' if correct else 'Incorrecta')
    }
