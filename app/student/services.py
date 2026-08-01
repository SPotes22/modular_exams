import random
from typing import Any, Dict, List, Optional
from app.extensions import db
from app.models import ExamAttempt, ExamQuestion, ExamSession, QuestionOption, StudentAnswer
from app.realtime.manager import session_manager


class StudentService:
    """
    Servicio encargado de la lógica de negocio para los estudiantes:
    recuperación de exámenes, preparación de preguntas en RAM y persistencia de resultados.
    """

    @staticmethod
    def get_and_prepare_session(session_code: str) -> Optional[ExamSession]:
        """
        Busca una sesión por código. Si existe en BD pero no está en la memoria RAM,
        carga las preguntas, las prepara y la registra en SessionManager.
        """
        clean_code = session_code.strip().upper()
        session_obj = ExamSession.query.filter_by(session_code=clean_code).first()

        if not session_obj:
            return None

        # Verificar si la sesión ya existe en memoria RAM; si no, inicializarla
        rt_session = session_manager.get_session_by_code(clean_code)
        if not rt_session:
            questions_data = StudentService._format_questions_for_memory(session_obj.exam)
            mode_name = getattr(session_obj.exam, 'exam_mode', 'open_navigation')
            
            session_manager.create_session(
                session_id=session_obj.id,
                session_code=clean_code,
                exam_id=session_obj.exam_id,
                instructor_id=session_obj.exam.instructor_id,
                mode_name=mode_name,
                questions=questions_data
            )

        return session_obj

    @staticmethod
    def _format_questions_for_memory(exam) -> List[Dict[str, Any]]:
        """Formatea y desordena (shuffle) las preguntas y opciones del examen para almacenarlas en RAM."""
        questions_data = []
        eq_list = list(exam.questions)
        random.shuffle(eq_list)

        for eq in eq_list:
            q = eq.question
            opts = []
            if hasattr(q, 'options') and q.options:
                opts_list = list(q.options)
                random.shuffle(opts_list)
                opts = [
                    {
                        "id": o.id,
                        "option_text": o.option_text,
                        "is_correct": o.is_correct
                    }
                    for o in opts_list
                ]

            questions_data.append({
                "id": q.id,
                "statement": q.statement,
                "question_type": q.question_type,
                "points": eq.points,
                "options": opts,
                "explanation": getattr(q, 'explanation', '')
            })

        return questions_data

    @staticmethod
    def save_final_attempt(student_id: int, session_id: int, answers_dict: Dict[int, Any]) -> ExamAttempt:
        """
        Persiste en la Base de Datos el intento final del estudiante leyendo el diccionario 
        de respuestas acumuladas en RAM.
        """
        session_obj = ExamSession.query.get_or_404(session_id)
        
        # Evitar duplicados si el estudiante ya registró un intento persistido
        existing_attempt = ExamAttempt.query.filter_by(student_id=student_id, session_id=session_id).first()
        if existing_attempt:
            return existing_attempt

        total_possible = 0.0
        earned = 0.0
        student_answers_to_db = []

        for eq in session_obj.exam.questions:
            q = eq.question
            total_possible += eq.points
            
            # Obtener lo que respondió el estudiante en esta pregunta desde la memoria RAM
            student_ans_data = answers_dict.get(q.id)
            is_correct = False
            selected_option_id = None

            if student_ans_data and isinstance(student_ans_data, dict):
                # Extraer según la estructura guardada por la modalidad
                selected_option_id = student_ans_data.get("answer_data", {}).get("option_id") or student_ans_data.get("option_id")
                if "is_correct" in student_ans_data:
                    is_correct = student_ans_data["is_correct"]
                elif selected_option_id:
                    opt = QuestionOption.query.get(selected_option_id)
                    if opt and opt.is_correct and opt.question_id == q.id:
                        is_correct = True

            if is_correct:
                earned += eq.points

            student_answers_to_db.append({
                "question_id": q.id,
                "selected_option_id": selected_option_id,
                "is_correct": is_correct
            })

        final_score = (earned / total_possible * 100.0) if total_possible > 0 else 0.0

        attempt = ExamAttempt(
            student_id=student_id,
            session_id=session_id,
            score=round(final_score, 2),
            status='completed'
        )
        db.session.add(attempt)
        db.session.flush()

        for ans in student_answers_to_db:
            sa = StudentAnswer(
                attempt_id=attempt.id,
                question_id=ans["question_id"],
                selected_option_id=ans["selected_option_id"],
                is_correct=ans["is_correct"]
            )
            db.session.add(sa)

        db.session.commit()
        return attempt
