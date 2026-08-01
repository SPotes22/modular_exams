import io
import random
from typing import Any, Dict, List, Optional
import pandas as pd
from app.extensions import db
from app.models import Exam, ExamAttempt, ExamQuestion, ExamSession, Question, QuestionOption


class ExamService:
    """
    Servicio encargado de la lógica de negocio del instructor:
    creación de exámenes, preparación de lobbies y generación de reportes en Excel.
    """

    @staticmethod
    def create_exam_from_bank(instructor_id: int, title: str, category: str, 
                               exam_mode: str, selected_question_ids: List[int]) -> Exam:
        """Crea un nuevo examen asociando preguntas existentes de un banco."""
        exam = Exam(
            title=title,
            category=category,
            instructor_id=instructor_id,
            exam_mode=exam_mode
        )
        db.session.add(exam)
        db.session.flush()

        for q_id in selected_question_ids:
            eq = ExamQuestion(
                exam_id=exam.id,
                question_id=q_id,
                points=1.0
            )
            db.session.add(eq)

        db.session.commit()
        return exam

    @staticmethod
    def create_session(exam_id: int, session_code: str) -> ExamSession:
        """Crea un registro de sesión de examen en base de datos."""
        clean_code = session_code.strip().upper()
        session_obj = ExamSession(
            exam_id=exam_id,
            session_code=clean_code,
            status='waiting'
        )
        db.session.add(session_obj)
        db.session.commit()
        return session_obj

    @staticmethod
    def generate_excel_report(session_id: int) -> io.BytesIO:
        """
        Procesa los intentos de una sesión de examen y genera un archivo Excel en memoria (io.BytesIO).
        """
        session_obj = ExamSession.query.get_or_404(session_id)
        attempts = ExamAttempt.query.filter_by(session_id=session_id).all()

        data = []
        for att in attempts:
            student_name = att.student.username if att.student else f"Estudiante #{att.student_id}"
            data.append({
                "ID Estudiante": att.student_id,
                "Nombre Usuario": student_name,
                "Puntaje (%)": att.score,
                "Estado": att.status,
                "Fecha": att.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(att, 'created_at') and att.created_at else "N/A"
            })

        df = pd.DataFrame(data if data else [{
            "ID Estudiante": "-", "Nombre Usuario": "Sin participantes", "Puntaje (%)": 0, "Estado": "-", "Fecha": "-"
        }])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=f"Sesion_{session_obj.session_code}")
        
        output.seek(0)
        return output
