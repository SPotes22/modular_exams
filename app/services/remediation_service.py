"""
app/services/remediation_service.py

Genera cursos de refuerzo automáticos (Learning Builder) para estudiantes
que reprobaron un examen (<40% de aprobación).

Flujo:
  1. Filtra estudiantes con score < 40
  2. Identifica preguntas fallidas y su metadata (categoría, enunciado, feedback)
  3. Construye un Learning con módulos por categoría y bloques por pregunta
  4. Asigna el curso SOLO a los estudiantes que lo necesitan
"""

from app.extensions import db
from app.models import (
    ExamSession, ExamAttempt, Learning, LearningModule, Lesson, Block, LearningProgress
)

PASSING_SCORE = 40  # umbral de aprobación en porcentaje


class RemediationService:

    @staticmethod
    def build_remediation_course(session_id: int, extra_student_ids: list[int] = None) -> Learning | None:
        """
        Punto de entrada principal. Recibe el id de sesión de examen y
        opcionalmente una lista de student_ids adicionales para incluir.

        Retorna el objeto Learning creado, o None si no hay datos suficientes.
        """
        session = ExamSession.query.get(session_id)
        if not session:
            return None

        # 1. Estudiantes que perdieron (<40%)
        failing_attempts = RemediationService._get_failing_attempts(session)

        # 2. Agregar extras si el docente los incluyó manualmente
        if extra_student_ids:
            extra = ExamAttempt.query.filter(
                ExamAttempt.session_id == session_id,
                ExamAttempt.student_id.in_(extra_student_ids),
                ~ExamAttempt.id.in_([a.id for a in failing_attempts])
            ).all()
            failing_attempts = failing_attempts + extra

        if not failing_attempts:
            return None

        # 3. Idempotencia: si ya se generó un curso para esta sesión (por ejemplo,
        # porque el auto-disparo y un click manual coincidieron), no duplicar el
        # curso — solo agregar a los estudiantes nuevos que falten.
        existing_course = Learning.query.filter_by(source_session_id=session_id).first()
        if existing_course:
            RemediationService._assign_to_students(existing_course, failing_attempts)
            db.session.commit()
            return existing_course

        # 4. Analizar preguntas fallidas agrupadas por categoría
        topics_by_category = RemediationService._analyze_failures(failing_attempts)

        if not topics_by_category:
            return None

        # 5. Construir el curso
        exam = session.exam
        course = RemediationService._build_course(
            title=f"Refuerzo: {exam.title}",
            description=f"Capacitación automática generada desde la sesión del {session.created_at.strftime('%d/%m/%Y')}. "
                        f"Basada en las preguntas con mayor índice de error.",
            topics_by_category=topics_by_category,
            owner_id=exam.instructor_id,
            source_session_id=session.id,
        )

        # 6. Asignar el curso a los estudiantes que lo necesitan
        RemediationService._assign_to_students(course, failing_attempts)

        db.session.commit()
        return course

    # -------------------------------------------------------------------------
    # Privados
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_failing_attempts(session) -> list:
        """Devuelve los intentos con score < PASSING_SCORE."""
        return [
            attempt for attempt in session.attempts
            if attempt.score is not None and attempt.score < PASSING_SCORE
        ]

    @staticmethod
    def _analyze_failures(attempts: list) -> dict:
        """
        Retorna:
        {
          "categoria_A": [
            {
              "question_id": 1,
              "text": "¿Cuál es...?",
              "category": "Redes",
              "feedback": "...",
              "correct_answer": "80",
              "options": [QuestionOption, ...],
              "wrong_answers": ["443", "443", "21"],   # lo que pusieron los estudiantes
            },
            ...
          ],
          ...
        }
        Solo incluye preguntas donde al menos 1 estudiante falló con respuesta
        no vacía (vacías se reportan pero no generan bloque de refuerzo).
        """
        # Recopila respuestas incorrectas por pregunta
        failure_map: dict[int, dict] = {}

        for attempt in attempts:
            for answer in attempt.answers:
                if answer.is_correct:
                    continue

                q = answer.question
                if q is None:
                    continue

                if q.id not in failure_map:
                    failure_map[q.id] = {
                        "question_id": q.id,
                        "text": answer.display_statement,
                        "category": q.category or "General",
                        "feedback": answer.display_feedback,
                        "correct_answer": answer.display_correct_answer,
                        "options": list(q.options),
                        "wrong_answers": [],
                        "empty_count": 0,
                    }

                student_answer = answer.selected_option_text or answer.answer_text
                if not student_answer and answer.selected_option:
                    student_answer = answer.selected_option.option_text

                if not student_answer or not student_answer.strip():
                    failure_map[q.id]["empty_count"] += 1
                else:
                    failure_map[q.id]["wrong_answers"].append(student_answer)

        # Filtra preguntas donde solo hubo respuestas vacías (no generan bloque)
        filtered = {
            qid: data for qid, data in failure_map.items()
            if data["wrong_answers"]  # al menos 1 respuesta real incorrecta
        }

        # Agrupa por categoría
        by_category: dict[str, list] = {}
        for data in filtered.values():
            cat = data["category"]
            by_category.setdefault(cat, []).append(data)

        return by_category

    @staticmethod
    def _build_course(title: str, description: str, topics_by_category: dict, owner_id: int, source_session_id: int) -> Learning:
        """
        Crea el objeto Learning con su estructura de módulos/lecciones/bloques.

        Estructura generada:
          Learning
            └── LearningModule  (1 por categoría)
                  └── Lesson    (1 por pregunta fallida)
                        └── Block tipo "text"      → explicación del tema
                        └── Block tipo "question"  → la pregunta para reforzar (si tiene opciones)
        """
        course = Learning(
            nombre=title,
            descripcion=description,
            autor_id=owner_id,
            estado='draft',   # el docente revisa antes de publicar
            source_session_id=source_session_id,
        )
        db.session.add(course)
        db.session.flush()  # obtener course.id

        for module_order, (category, questions) in enumerate(topics_by_category.items(), start=1):
            module = LearningModule(
                learning_id=course.id,
                titulo=f"Módulo: {category}",
                orden=module_order,
            )
            db.session.add(module)
            db.session.flush()

            lesson = Lesson(
                module_id=module.id,
                titulo=f"Repaso de {category}",
                orden=1,
            )
            db.session.add(lesson)
            db.session.flush()

            block_order = 1
            for q_data in questions:
                # Bloque 1: explicación contextual del error
                text_block = Block(
                    lesson_id=lesson.id,
                    tipo="text",
                    orden=block_order,
                    configuracion=RemediationService._build_explanation_content(q_data),
                )
                db.session.add(text_block)
                block_order += 1

                # Bloque 2: pregunta de refuerzo (solo si la pregunta original tiene opciones)
                if q_data["options"]:
                    quiz_block = Block(
                        lesson_id=lesson.id,
                        tipo="question",
                        orden=block_order,
                        configuracion=RemediationService._build_quiz_content(q_data),
                    )
                    db.session.add(quiz_block)
                    block_order += 1

        return course

    @staticmethod
    def _build_explanation_content(q_data: dict) -> dict:
        """
        Genera la configuración de un bloque de texto explicativo, en el
        formato que ya entiende el Learning Builder (`tipo == "text"`).
        """
        wrong_sample = ", ".join(sorted(set(q_data["wrong_answers"][:3])))  # máx 3 únicas

        html = (
            f"<p><strong>Pregunta:</strong> {q_data['text']}</p>"
            f"<p>En la evaluación, las respuestas incorrectas más frecuentes fueron: {wrong_sample}.</p>"
            f"<p><strong>Respuesta correcta:</strong> {q_data['correct_answer']}</p>"
        )
        if q_data.get("feedback"):
            html += f"<p>{q_data['feedback']}</p>"

        return {"content": html}

    @staticmethod
    def _build_quiz_content(q_data: dict) -> dict:
        """
        Genera la configuración de un bloque tipo "question" (opción múltiple),
        compatible con `learning_service.grade_question_block`.
        """
        options = [
            {"id": idx, "text": opt.option_text, "is_correct": bool(opt.is_correct)}
            for idx, opt in enumerate(q_data["options"], start=1)
        ]
        return {
            "question_type": "multiple_choice",
            "question": q_data["text"],
            "points": 10.0,
            "feedback": q_data.get("feedback") or "",
            "explanation": f"Pregunta de refuerzo generada desde la evaluación (id original: {q_data['question_id']}).",
            "hints": [],
            "timer": 0,
            "options": options,
        }

    @staticmethod
    def _assign_to_students(course: Learning, attempts: list) -> None:
        """
        Crea un LearningProgress (estado inicial) para cada estudiante
        que debe completar el curso de refuerzo.
        El curso no es visible para nadie más (queda en 'draft' hasta publicarse).
        """
        student_ids = {a.student_id for a in attempts if a.student_id}
        already_assigned = {
            p.user_id for p in LearningProgress.query.filter_by(learning_id=course.id).all()
        }

        for student_id in student_ids - already_assigned:
            progress = LearningProgress(
                learning_id=course.id,
                user_id=student_id,
                completed=False,
            )
            db.session.add(progress)
