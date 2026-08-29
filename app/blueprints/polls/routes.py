"""
Rutas REST para Polls (encuestas en vivo).
No usa CSRF porque la app usa flask-session, no JWT.
La protección anti-doble-voto se hace por student_id (FK única en PollVote).
"""
from flask import jsonify, request, session
from flask_login import current_user, login_required
from app.extensions import db, socketio
from app.models import Poll, PollVote
from app.blueprints.polls import polls_bp


# ── Instructor: crear encuesta ──────────────────────────────────────────────
@polls_bp.route('/polls/create', methods=['POST'])
@login_required
def create_poll():
    if current_user.role not in ('instructor', 'superuser', 'admin'):
        return jsonify({'error': 'Acceso denegado'}), 403

    data = request.get_json(silent=True) or request.form
    poll_type   = data.get('poll_type', 'poll')          # poll|true_false|multiple_choice|open_answer
    question    = (data.get('question_text') or '').strip()
    room_code   = (data.get('room_code') or '').strip().upper()
    options_raw = data.get('options')                    # list o None

    if not question or not room_code:
        return jsonify({'error': 'question_text y room_code son obligatorios'}), 400

    # Normaliza opciones según tipo
    if poll_type == 'true_false':
        options = ['Verdadero', 'Falso']
    elif poll_type == 'multiple_choice':
        if isinstance(options_raw, list):
            options = [str(o).strip() for o in options_raw if str(o).strip()]
        else:
            options = []
        if not options:
            return jsonify({'error': 'Se requieren opciones para selección múltiple'}), 400
    else:
        options = None  # open_answer y poll libre

    poll = Poll(
        instructor_id=current_user.id,
        room_code=room_code,
        poll_type=poll_type,
        question_text=question,
        options_json=options,
        status='open',
    )
    db.session.add(poll)
    db.session.commit()

    payload = _poll_payload(poll)
    # Emitir a todos los estudiantes de la sala
    socketio.emit('poll_launched', payload, to=f'room_{room_code}')
    # Emitir al instructor (sala teacher_<id>)
    socketio.emit('poll_launched', payload, to=f'teacher_{current_user.id}')

    return jsonify({'ok': True, 'poll': payload}), 201


# ── Estudiante: votar ───────────────────────────────────────────────────────
@polls_bp.route('/polls/<int:poll_id>/vote', methods=['POST'])
@login_required
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    if poll.status != 'open':
        return jsonify({'error': 'La encuesta ya fue cerrada'}), 409

    # Verificar si ya votó (la constraint DB también lo bloquea, pero damos error claro)
    already = PollVote.query.filter_by(poll_id=poll_id, student_id=current_user.id).first()
    if already:
        return jsonify({'error': 'Ya votaste en esta encuesta', 'already_voted': True}), 409

    data = request.get_json(silent=True) or request.form
    answer = (data.get('answer') or '').strip()
    if not answer:
        return jsonify({'error': 'Respuesta vacía'}), 400

    # Para tipos con opciones fijas, validar que la respuesta sea válida
    if poll.poll_type in ('true_false', 'multiple_choice') and poll.options_json:
        if answer not in poll.options_json:
            return jsonify({'error': 'Opción inválida'}), 400

    vote_obj = PollVote(poll_id=poll_id, student_id=current_user.id, answer_text=answer)
    try:
        db.session.add(vote_obj)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Ya votaste en esta encuesta', 'already_voted': True}), 409

    # Emitir resultados actualizados al instructor y a la sala
    _broadcast_results(poll)

    return jsonify({'ok': True, 'vote_count': poll.vote_count})


# ── Instructor: cerrar encuesta ─────────────────────────────────────────────
@polls_bp.route('/polls/<int:poll_id>/close', methods=['POST'])
@login_required
def close_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    if poll.instructor_id != current_user.id:
        return jsonify({'error': 'Acceso denegado'}), 403

    poll.status = 'closed'
    db.session.commit()

    payload = _poll_payload(poll)
    socketio.emit('poll_closed', payload, to=f'room_{poll.room_code}')
    socketio.emit('poll_closed', payload, to=f'teacher_{current_user.id}')
    return jsonify({'ok': True})


# ── Resultados en tiempo real (GET) ─────────────────────────────────────────
@polls_bp.route('/polls/<int:poll_id>/results')
@login_required
def poll_results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    return jsonify(_poll_payload(poll))


# ── helpers ──────────────────────────────────────────────────────────────────
def _poll_payload(poll):
    return {
        'id': poll.id,
        'room_code': poll.room_code,
        'poll_type': poll.poll_type,
        'question_text': poll.question_text,
        'options': poll.options_json,
        'status': poll.status,
        'vote_count': poll.vote_count,
        'results': poll.results(),
    }


def _broadcast_results(poll):
    payload = _poll_payload(poll)
    socketio.emit('poll_results_updated', payload, to=f'room_{poll.room_code}')
    socketio.emit('poll_results_updated', payload, to=f'teacher_{poll.instructor_id}')
