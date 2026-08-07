# app/services/learning_service.py
import json
from datetime import datetime
from app.extensions import db
from app.models import Learning, LearningModule, Lesson, Block, LearningProgress, BlockAnswer

def create_default_learning(autor_id, nombre, descripcion=None, portada=None):
    learning = Learning(
        nombre=nombre,
        descripcion=descripcion or "Capacitación interactiva basada en bloques",
        estado='draft',
        portada=portada,
        autor_id=autor_id
    )
    db.session.add(learning)
    db.session.flush()

    # Módulo inicial por defecto
    default_module = LearningModule(
        learning_id=learning.id,
        titulo="Módulo 1: Introducción",
        descripcion="Fundamentos e introducción",
        orden=1
    )
    db.session.add(default_module)
    db.session.flush()

    # Lección inicial por defecto
    default_lesson = Lesson(
        module_id=default_module.id,
        titulo="Lección 1: Bienvenido",
        descripcion="Contenido inicial",
        orden=1
    )
    db.session.add(default_lesson)
    db.session.flush()

    # Bloque de bienvenida por defecto
    default_block = Block(
        lesson_id=default_lesson.id,
        tipo='title',
        orden=1,
        visible=True,
        configuracion={
            'title': '¡Bienvenido a la capacitación!',
            'subtitle': 'Comienza a explorar los bloques interactivos.',
            'level': 'h1'
        }
    )
    db.session.add(default_block)
    db.session.commit()
    return learning


def duplicate_learning(learning_id, new_autor_id):
    original = Learning.query.get_or_404(learning_id)
    new_learning = Learning(
        nombre=f"{original.nombre} (Copia)",
        descripcion=original.descripcion,
        estado='draft',
        portada=original.portada,
        autor_id=new_autor_id
    )
    db.session.add(new_learning)
    db.session.flush()

    for orig_mod in original.modules:
        new_mod = LearningModule(
            learning_id=new_learning.id,
            titulo=orig_mod.titulo,
            descripcion=orig_mod.descripcion,
            orden=orig_mod.orden
        )
        db.session.add(new_mod)
        db.session.flush()

        for orig_les in orig_mod.lessons:
            new_les = Lesson(
                module_id=new_mod.id,
                titulo=orig_les.titulo,
                descripcion=orig_les.descripcion,
                orden=orig_les.orden
            )
            db.session.add(new_les)
            db.session.flush()

            for orig_block in orig_les.blocks:
                new_block = Block(
                    lesson_id=new_les.id,
                    tipo=orig_block.tipo,
                    orden=orig_block.orden,
                    visible=orig_block.visible,
                    configuracion=json.loads(json.dumps(orig_block.configuracion))
                )
                db.session.add(new_block)

    db.session.commit()
    return new_learning


def export_learning_json(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    data = {
        "version": "1.0",
        "nombre": learning.nombre,
        "descripcion": learning.descripcion,
        "portada": learning.portada,
        "modules": []
    }

    for mod in learning.modules:
        mod_data = {
            "titulo": mod.titulo,
            "descripcion": mod.descripcion,
            "orden": mod.orden,
            "lessons": []
        }
        for les in mod.lessons:
            les_data = {
                "titulo": les.titulo,
                "descripcion": les.descripcion,
                "orden": les.orden,
                "blocks": []
            }
            for blk in les.blocks:
                blk_data = {
                    "tipo": blk.tipo,
                    "orden": blk.orden,
                    "visible": blk.visible,
                    "configuracion": blk.configuracion
                }
                les_data["blocks"].append(blk_data)
            mod_data["lessons"].append(les_data)
        data["modules"].append(mod_data)

    return data


def import_learning_json(data, autor_id):
    nombre = data.get("nombre", "Capacitación Importada")
    descripcion = data.get("descripcion", "")
    portada = data.get("portada")

    learning = Learning(
        nombre=f"{nombre} (Importado)",
        descripcion=descripcion,
        estado='draft',
        portada=portada,
        autor_id=autor_id
    )
    db.session.add(learning)
    db.session.flush()

    modules_data = data.get("modules", [])
    for m_idx, mod_data in enumerate(modules_data, 1):
        mod = LearningModule(
            learning_id=learning.id,
            titulo=mod_data.get("titulo", f"Módulo {m_idx}"),
            descripcion=mod_data.get("descripcion", ""),
            orden=mod_data.get("orden", m_idx)
        )
        db.session.add(mod)
        db.session.flush()

        lessons_data = mod_data.get("lessons", [])
        for l_idx, les_data in enumerate(lessons_data, 1):
            les = Lesson(
                module_id=mod.id,
                titulo=les_data.get("titulo", f"Lección {l_idx}"),
                descripcion=les_data.get("descripcion", ""),
                orden=les_data.get("orden", l_idx)
            )
            db.session.add(les)
            db.session.flush()

            blocks_data = les_data.get("blocks", [])
            for b_idx, blk_data in enumerate(blocks_data, 1):
                blk = Block(
                    lesson_id=les.id,
                    tipo=blk_data.get("tipo", "text"),
                    orden=blk_data.get("orden", b_idx),
                    visible=blk_data.get("visible", True),
                    configuracion=blk_data.get("configuracion", {})
                )
                db.session.add(blk)

    db.session.commit()
    return learning


def default_block_config(tipo):
    """Retorna la configuración por defecto según el tipo de bloque."""
    if tipo == 'title':
        return {
            "title": "Nuevo Título",
            "subtitle": "Subtítulo de la sección",
            "level": "h2"
        }
    elif tipo == 'text':
        return {
            "content": "<p>Escribe tu contenido enriquecido aquí...</p>"
        }
    elif tipo == 'image':
        return {
            "src": "",
            "alt": "Imagen",
            "caption": "Pie de imagen",
            "alignment": "center"
        }
    elif tipo == 'video':
        return {
            "video_type": "url",  # 'url' (YouTube/Vimeo) o 'local'
            "url": "",
            "caption": "Descripción del video",
            "autoplay": False
        }
    elif tipo == 'question':
        return {
            "question_type": "multiple_choice",  # 'multiple_choice', 'single_choice', 'true_false', 'short_answer', 'fill_blank', 'ordering', 'matching'
            "question": "¿Cuál es la respuesta correcta?",
            "points": 10.0,
            "feedback": "¡Excelente trabajo!",
            "explanation": "Explicación detallada del concepto.",
            "hints": ["Pista 1: Revisa el concepto del capítulo."],
            "timer": 0,  # segundos, 0 deshabilitado
            "options": [
                {"id": 1, "text": "Opción A", "is_correct": True},
                {"id": 2, "text": "Opción B", "is_correct": False}
            ],
            "correct_answer_tf": True,
            "short_answers": ["respuesta correcta"],
            "fill_text": "El agua hierva a [[100]] grados centígrados.",
            "order_items": [
                {"id": 1, "text": "Primer paso", "correct_pos": 1},
                {"id": 2, "text": "Segundo paso", "correct_pos": 2}
            ],
            "matching_pairs": [
                {"id": 1, "left": "HTML", "right": "Lenguaje de marcado"},
                {"id": 2, "left": "CSS", "right": "Hojas de estilo"}
            ]
        }
    elif tipo == 'divider':
        return {
            "style": "solid",  # 'solid', 'dashed', 'dotted'
            "spacing": "medium"
        }
    elif tipo == 'quote':
        return {
            "text": "La educación es la clave para abrir la puerta de la libertad.",
            "author": "George Washington Carver",
            "style": "info"  # 'info', 'warning', 'note', 'quote'
        }
    elif tipo == 'pdf':
        return {
            "src": "",
            "title": "Documento PDF",
            "downloadable": True
        }
    elif tipo == 'download':
        return {
            "src": "",
            "filename": "archivo.pdf",
            "title": "Recurso descargable",
            "description": "Haz clic para descargar el recurso suplementario."
        }
    elif tipo == 'audio':
        return {
            "src": "",
            "title": "Narración / Podcast",
            "author": "Instructor"
        }
    elif tipo == 'embed':
        return {
            "url": "",
            "iframe_code": "",
            "title": "Contenido embebido",
            "height": "400px"
        }
    return {}


def grade_question_block(block, student_answer):
    cfg = block.configuracion or {}
    qtype = cfg.get("question_type", "single_choice")
    max_points = float(cfg.get("points", 10.0))
    feedback = cfg.get("feedback", "")
    explanation = cfg.get("explanation", "")

    is_correct = False
    earned_points = 0.0

    if qtype in ['single_choice', 'multiple_choice']:
        # student_answer = list of selected option IDs or single ID
        selected_ids = student_answer.get("selected_options", [])
        if isinstance(selected_ids, (int, str)):
            selected_ids = [int(selected_ids)]
        else:
            selected_ids = [int(x) for x in selected_ids]

        options = cfg.get("options", [])
        correct_ids = [opt["id"] for opt in options if opt.get("is_correct")]

        if set(selected_ids) == set(correct_ids) and len(correct_ids) > 0:
            is_correct = True
            earned_points = max_points

    elif qtype == 'true_false':
        user_val = student_answer.get("true_false_val")
        correct_val = cfg.get("correct_answer_tf", True)
        if user_val is not None and bool(user_val) == bool(correct_val):
            is_correct = True
            earned_points = max_points

    elif qtype == 'short_answer':
        text_resp = (student_answer.get("text_response") or "").strip().lower()
        valid_answers = [ans.strip().lower() for ans in cfg.get("short_answers", [])]
        if text_resp in valid_answers:
            is_correct = True
            earned_points = max_points

    elif qtype == 'fill_blank':
        # user answers dictionary key -> string
        user_blanks = student_answer.get("blanks", {})
        # Compare with expected values
        expected = student_answer.get("expected_blanks", {})
        correct_count = 0
        total_blanks = len(expected)
        if total_blanks > 0:
            for k, val in expected.items():
                if user_blanks.get(str(k), "").strip().lower() == val.strip().lower():
                    correct_count += 1
            if correct_count == total_blanks:
                is_correct = True
                earned_points = max_points
            else:
                earned_points = round((correct_count / total_blanks) * max_points, 2)

    elif qtype == 'ordering':
        submitted_order = student_answer.get("order", [])  # list of item IDs in submitted order
        expected_items = sorted(cfg.get("order_items", []), key=lambda x: x.get("correct_pos", 1))
        expected_ids = [item["id"] for item in expected_items]
        if [int(x) for x in submitted_order] == expected_ids:
            is_correct = True
            earned_points = max_points

    elif qtype == 'matching':
        submitted_pairs = student_answer.get("pairs", {})  # dict left_id -> right_text
        pairs_list = cfg.get("matching_pairs", [])
        correct_count = 0
        total_pairs = len(pairs_list)
        if total_pairs > 0:
            for p in pairs_list:
                left_id = str(p["id"])
                if submitted_pairs.get(left_id) == p["right"]:
                    correct_count += 1
            if correct_count == total_pairs:
                is_correct = True
                earned_points = max_points
            else:
                earned_points = round((correct_count / total_pairs) * max_points, 2)

    return {
        "is_correct": is_correct,
        "score": earned_points,
        "max_points": max_points,
        "feedback": feedback,
        "explanation": explanation
    }


def update_student_progress(user_id, learning_id, lesson_id=None, block_id=None, time_delta=0):
    progress = LearningProgress.query.filter_by(user_id=user_id, learning_id=learning_id).first()
    if not progress:
        progress = LearningProgress(
            user_id=user_id,
            learning_id=learning_id,
            current_lesson_id=lesson_id,
            current_block_id=block_id,
            progress_percent=0.0,
            time_spent_seconds=0,
            score=0.0,
            completed=False
        )
        db.session.add(progress)

    if lesson_id:
        progress.current_lesson_id = lesson_id
    if block_id:
        progress.current_block_id = block_id

    if time_delta > 0:
        progress.time_spent_seconds = (progress.time_spent_seconds or 0) + time_delta

    # Recalculate percent & total score
    learning = Learning.query.get(learning_id)
    all_lessons = []
    total_blocks = 0
    for mod in sorted(learning.modules, key=lambda m: m.orden or 0):
        for les in sorted(mod.lessons, key=lambda l: l.orden or 0):
            all_lessons.append(les)
            total_blocks += len(les.blocks)

    # Count answered questions & average score
    answers = BlockAnswer.query.join(Block).join(Lesson).join(LearningModule).filter(
        LearningModule.learning_id == learning_id,
        BlockAnswer.user_id == user_id
    ).all()

    if answers:
        total_score = sum(ans.score for ans in answers)
        progress.score = round(total_score, 2)

    if total_blocks > 0:
        # Calculate completion ratio based on current lesson position or answered blocks
        completed_lessons = 0
        if lesson_id and all_lessons:
            lesson_ids = [l.id for l in all_lessons]
            if lesson_id in lesson_ids:
                curr_idx = lesson_ids.index(lesson_id) + 1
                progress.progress_percent = min(100.0, round((curr_idx / len(all_lessons)) * 100.0, 1))
                if curr_idx == len(all_lessons):
                    progress.completed = True

    progress.last_activity = datetime.utcnow()
    db.session.commit()
    return progress
