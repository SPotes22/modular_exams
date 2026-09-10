"""
app/services/remediation_service.py

Genera cursos de refuerzo automáticos (Learning Builder) para estudiantes
que reprobaron un examen (<40% de aprobación).

Flujo:
  1. Filtra estudiantes con score < 40
  2. Identifica preguntas fallidas y su metadata (categoría, tema, dificultad)
  3. Construye un Learning con módulos por categoría y bloques por pregunta
  4. Asigna el curso SOLO a los estudiantes que lo necesitan
"""

from app.extensions import db
from app.models import (
    ExamSession, ExamAttempt, ExamQuestion, Question,
    Learning, LearningModule, Lesson, Block, LearningProgress
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

        # 3. Analizar preguntas fallidas agrupadas por categoría
        topics_by_category = RemediationService._analyze_failures(failing_attempts)

        if not topics_by_category:
            return None

        # 4. Construir el curso
        exam = session.exam
        course = RemediationService._build_course(
            title=f"Refuerzo: {exam.title}",
            description=f"Capacitación automática generada desde la sesión del {session.created_at.strftime('%d/%m/%Y')}. "
                        f"Basada en las preguntas con mayor índice de error.",
            topics_by_category=topics_by_category,
            owner_id=exam.owner_id,
        )

        # 5. Asignar el curso a los estudiantes que lo necesitan
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
              "topic": "tema X",
              "difficulty": "media",
              "correct_answer": "B",
              "wrong_answers": ["A", "A", "C"],   # lo que pusieron los estudiantes
              "related_material": "..."
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

                eq: ExamQuestion = answer.exam_question
                q: Question = eq.question

                if q.id not in failure_map:
                    failure_map[q.id] = {
                        "question_id": q.id,
                        "text": q.text,
                        "topic": getattr(q, "topic", "General"),
                        "category": getattr(q, "category", "Sin categoría"),
                        "difficulty": getattr(q, "difficulty", "media"),
                        "correct_answer": q.correct_answer,
                        "related_material": getattr(q, "related_material", ""),
                        "wrong_answers": [],
                        "empty_count": 0,
                    }

                student_answer = answer.student_answer or ""
                if not student_answer.strip():
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
    def _build_course(title: str, description: str, topics_by_category: dict, owner_id: int) -> Learning:
        """
        Crea el objeto Learning con su estructura de módulos/lecciones/bloques.

        Estructura generada:
          Learning
            └── LearningModule  (1 por categoría)
                  └── Lesson    (1 por pregunta fallida)
                        └── Block tipo "text"   → explicación del tema
                        └── Block tipo "quiz"   → la pregunta para reforzar
        """
        course = Learning(
            title=title,
            description=description,
            owner_id=owner_id,
            is_published=False,   # el docente revisa antes de publicar
        )
        db.session.add(course)
        db.session.flush()  # obtener course.id

        for module_order, (category, questions) in enumerate(topics_by_category.items()):
            module = LearningModule(
                learning_id=course.id,
                title=f"Módulo: {category}",
                order_index=module_order,
            )
            db.session.add(module)
            db.session.flush()

            lesson = Lesson(
                module_id=module.id,
                title=f"Repaso de {category}",
                order_index=0,
            )
            db.session.add(lesson)
            db.session.flush()

            for block_order, q_data in enumerate(questions):
                # Bloque 1: explicación contextual del error
                text_block = Block(
                    lesson_id=lesson.id,
                    type="text",
                    order_index=block_order * 2,
                    content=RemediationService._build_explanation_content(q_data),
                )
                db.session.add(text_block)

                # Bloque 2: pregunta de refuerzo
                quiz_block = Block(
                    lesson_id=lesson.id,
                    type="quiz",
                    order_index=block_order * 2 + 1,
                    content=RemediationService._build_quiz_content(q_data),
                )
                db.session.add(quiz_block)

        return course

    @staticmethod
    def _build_explanation_content(q_data: dict) -> dict:
        """
        Genera el JSON de contenido para un bloque de texto explicativo.
        Usa el formato que ya entiende el Learning Builder existente.
        """
        wrong_sample = ", ".join(set(q_data["wrong_answers"][:3]))  # máx 3 únicas
        material = q_data.get("related_material", "")

        text = (
            f"**Tema:** {q_data['topic']}  \n"
            f"**Dificultad:** {q_data['difficulty']}  \n\n"
            f"En la evaluación, la pregunta *\"{q_data['text']}\"* tuvo respuestas frecuentes incorrectas como: {wrong_sample}.  \n\n"
            f"Revisemos este concepto antes de intentarlo de nuevo."
        )
        if material:
            text += f"\n\n📎 Material de referencia: {material}"

        return {"html": text}

    @staticmethod
    def _build_quiz_content(q_data: dict) -> dict:
        """
        Genera el JSON de contenido para un bloque tipo quiz.
        Compatible con el formato de bloques del Learning Builder.
        """
        return {
            "question": q_data["text"],
            "correct_answer": q_data["correct_answer"],
            "source_question_id": q_data["question_id"],  # trazabilidad
        }

    @staticmethod
    def _assign_to_students(course: Learning, attempts: list) -> None:
        """
        Crea un LearningProgress (estado inicial) para cada estudiante
        que debe completar el curso de refuerzo.
        El curso no es visible para nadie más.
        """
        student_ids = {a.student_id for a in attempts if a.student_id}

        for student_id in student_ids:
            progress = LearningProgress(
                learning_id=course.id,
                student_id=student_id,
                completed=False,
            )
            db.session.add(progress)
