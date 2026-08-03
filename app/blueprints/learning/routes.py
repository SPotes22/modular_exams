import os
import json
import uuid
from werkzeug.utils import secure_filename
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from app.extensions import db, socketio
from app.models import Learning, LearningModule, Lesson, Block, LearningProgress, BlockAnswer
from app.blueprints.learning import learning_bp
from app.services import learning_service

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'webm', 'pdf', 'mp3'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# VISTAS INSTRUCTOR
# ==========================================

@learning_bp.route('/instructor/dashboard')
@login_required
def instructor_dashboard():
    if current_user.role not in ['instructor', 'admin', 'superuser']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('auth.home'))

    learnings = Learning.query.filter_by(autor_id=current_user.id).order_by(Learning.fecha_creacion.desc()).all()
    return render_template('learning/instructor_dashboard.html', learnings=learnings)


@learning_bp.route('/instructor/create', methods=['POST'])
@login_required
def create_learning():
    if current_user.role not in ['instructor', 'admin', 'superuser']:
        return jsonify({'error': 'Acceso no autorizado'}), 403

    nombre = request.form.get('nombre', '').strip()
    descripcion = request.form.get('descripcion', '').strip()
    portada = None

    if 'portada_file' in request.files:
        file = request.files['portada_file']
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            fname = f"cover_{uuid.uuid4().hex}.{ext}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'learning')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, fname))
            portada = f"uploads/learning/{fname}"

    if not nombre:
        flash('El nombre de la capacitación es obligatorio.', 'warning')
        return redirect(url_for('learning.instructor_dashboard'))

    learning = learning_service.create_default_learning(
        autor_id=current_user.id,
        nombre=nombre,
        descripcion=descripcion,
        portada=portada
    )
    flash(f'Capacitación "{nombre}" creada correctamente.', 'success')
    return redirect(url_for('learning.builder', learning_id=learning.id))


@learning_bp.route('/instructor/edit/<int:learning_id>', methods=['POST'])
@login_required
def edit_learning(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    if learning.autor_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    learning.nombre = request.form.get('nombre', learning.nombre).strip()
    learning.descripcion = request.form.get('descripcion', learning.descripcion).strip()

    if 'portada_file' in request.files:
        file = request.files['portada_file']
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            fname = f"cover_{uuid.uuid4().hex}.{ext}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'learning')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, fname))
            learning.portada = f"uploads/learning/{fname}"

    db.session.commit()
    flash('Información general actualizada.', 'success')
    return redirect(url_for('learning.builder', learning_id=learning.id))


@learning_bp.route('/instructor/delete/<int:learning_id>', methods=['POST'])
@login_required
def delete_learning(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    if learning.autor_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    db.session.delete(learning)
    db.session.commit()
    flash('Capacitación eliminada.', 'success')
    return redirect(url_for('learning.instructor_dashboard'))


@learning_bp.route('/instructor/duplicate/<int:learning_id>', methods=['POST'])
@login_required
def duplicate_learning(learning_id):
    if current_user.role not in ['instructor', 'admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    new_learning = learning_service.duplicate_learning(learning_id, current_user.id)
    flash(f'Capacitación duplicada exitosamente como "{new_learning.nombre}".', 'success')
    return redirect(url_for('learning.instructor_dashboard'))


@learning_bp.route('/instructor/toggle-publish/<int:learning_id>', methods=['POST'])
@login_required
def toggle_publish(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    if learning.autor_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        return jsonify({'error': 'Acceso no autorizado'}), 403

    learning.estado = 'published' if learning.estado == 'draft' else 'draft'
    db.session.commit()
    return jsonify({'success': True, 'nuevo_estado': learning.estado})


@learning_bp.route('/instructor/export/<int:learning_id>')
@login_required
def export_learning(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    if learning.autor_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    data = learning_service.export_learning_json(learning_id)
    filename = f"learning_{learning.id}_{secure_filename(learning.nombre)}.json"
    
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'exports')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return send_file(filepath, as_attachment=True, download_name=filename)


@learning_bp.route('/instructor/import', methods=['POST'])
@login_required
def import_learning():
    if current_user.role not in ['instructor', 'admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    if 'json_file' not in request.files:
        flash('No se subió ningún archivo.', 'warning')
        return redirect(url_for('learning.instructor_dashboard'))

    file = request.files['json_file']
    if file and file.filename.endswith('.json'):
        try:
            content = json.load(file)
            imported = learning_service.import_learning_json(content, current_user.id)
            flash(f'Capacitación "{imported.nombre}" importada con éxito.', 'success')
            return redirect(url_for('learning.builder', learning_id=imported.id))
        except Exception as e:
            flash(f'Error al procesar el archivo JSON: {str(e)}', 'danger')
    else:
        flash('Formato de archivo no válido. Se requiere archivo JSON.', 'warning')

    return redirect(url_for('learning.instructor_dashboard'))


@learning_bp.route('/instructor/builder/<int:learning_id>')
@login_required
def builder(learning_id):
    if current_user.role not in ['instructor', 'admin', 'superuser']:
        flash('Acceso no autorizado', 'danger')
        return redirect(url_for('auth.home'))

    learning = Learning.query.get_or_404(learning_id)
    if learning.autor_id != current_user.id and current_user.role not in ['admin', 'superuser']:
        flash('Acceso denegado', 'danger')
        return redirect(url_for('learning.instructor_dashboard'))

    blocks_map = {
        les.id: [{
            "id": blk.id,
            "lesson_id": blk.lesson_id,
            "tipo": blk.tipo,
            "orden": blk.orden,
            "visible": blk.visible,
            "configuracion": blk.configuracion or {}
        } for blk in les.blocks]
        for mod in learning.modules for les in mod.lessons
    }

    return render_template('learning/builder.html', learning=learning, blocks_map=blocks_map)


# ==========================================
# API DE ESTRUCTURA Y BLOQUES (AJAX)
# ==========================================

@learning_bp.route('/api/module/create', methods=['POST'])
@login_required
def api_create_module():
    learning_id = request.form.get('learning_id', type=int)
    titulo = request.form.get('titulo', 'Nuevo Módulo').strip()
    
    learning = Learning.query.get_or_404(learning_id)
    max_order = db.session.query(db.func.max(LearningModule.orden)).filter_by(learning_id=learning_id).scalar() or 0

    new_mod = LearningModule(
        learning_id=learning_id,
        titulo=titulo,
        orden=max_order + 1
    )
    db.session.add(new_mod)
    db.session.flush()

    # Lección inicial por defecto en el nuevo módulo
    new_les = Lesson(
        module_id=new_mod.id,
        titulo="Lección 1",
        orden=1
    )
    db.session.add(new_les)
    db.session.commit()

    return jsonify({
        'success': True,
        'module': {'id': new_mod.id, 'titulo': new_mod.titulo, 'orden': new_mod.orden},
        'lesson': {'id': new_les.id, 'titulo': new_les.titulo, 'orden': new_les.orden}
    })


@learning_bp.route('/api/module/update/<int:module_id>', methods=['POST'])
@login_required
def api_update_module(module_id):
    mod = LearningModule.query.get_or_404(module_id)
    mod.titulo = request.form.get('titulo', mod.titulo).strip()
    mod.descripcion = request.form.get('descripcion', mod.descripcion).strip()
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/module/delete/<int:module_id>', methods=['POST'])
@login_required
def api_delete_module(module_id):
    mod = LearningModule.query.get_or_404(module_id)
    db.session.delete(mod)
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/lesson/create', methods=['POST'])
@login_required
def api_create_lesson():
    module_id = request.form.get('module_id', type=int)
    titulo = request.form.get('titulo', 'Nueva Lección').strip()

    mod = LearningModule.query.get_or_404(module_id)
    max_order = db.session.query(db.func.max(Lesson.orden)).filter_by(module_id=module_id).scalar() or 0

    new_les = Lesson(
        module_id=module_id,
        titulo=titulo,
        orden=max_order + 1
    )
    db.session.add(new_les)
    db.session.commit()

    return jsonify({
        'success': True,
        'lesson': {'id': new_les.id, 'titulo': new_les.titulo, 'orden': new_les.orden}
    })


@learning_bp.route('/api/lesson/update/<int:lesson_id>', methods=['POST'])
@login_required
def api_update_lesson(lesson_id):
    les = Lesson.query.get_or_404(lesson_id)
    les.titulo = request.form.get('titulo', les.titulo).strip()
    les.descripcion = request.form.get('descripcion', les.descripcion).strip()
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/lesson/delete/<int:lesson_id>', methods=['POST'])
@login_required
def api_delete_lesson(lesson_id):
    les = Lesson.query.get_or_404(lesson_id)
    db.session.delete(les)
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/block/create', methods=['POST'])
@login_required
def api_create_block():
    lesson_id = request.form.get('lesson_id', type=int)
    tipo = request.form.get('tipo', 'text')

    les = Lesson.query.get_or_404(lesson_id)
    max_order = db.session.query(db.func.max(Block.orden)).filter_by(lesson_id=lesson_id).scalar() or 0

    cfg = learning_service.default_block_config(tipo)

    block = Block(
        lesson_id=lesson_id,
        tipo=tipo,
        orden=max_order + 1,
        visible=True,
        configuracion=cfg
    )
    db.session.add(block)
    db.session.commit()

    return jsonify({
        'success': True,
        'block': {
            'id': block.id,
            'lesson_id': block.lesson_id,
            'tipo': block.tipo,
            'orden': block.orden,
            'visible': block.visible,
            'configuracion': block.configuracion
        }
    })


@learning_bp.route('/api/block/update/<int:block_id>', methods=['POST'])
@login_required
def api_update_block(block_id):
    block = Block.query.get_or_404(block_id)
    
    if 'visible' in request.form:
        block.visible = request.form.get('visible') in ['true', '1', 'True']

    if 'configuracion' in request.form:
        try:
            cfg = json.loads(request.form.get('configuracion'))
            block.configuracion = cfg
        except Exception as e:
            return jsonify({'error': f'JSON no válido: {str(e)}'}), 400

    db.session.commit()
    return jsonify({
        'success': True,
        'block': {
            'id': block.id,
            'visible': block.visible,
            'configuracion': block.configuracion
        }
    })


@learning_bp.route('/api/block/delete/<int:block_id>', methods=['POST'])
@login_required
def api_delete_block(block_id):
    block = Block.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/block/duplicate/<int:block_id>', methods=['POST'])
@login_required
def api_duplicate_block(block_id):
    original = Block.query.get_or_404(block_id)
    max_order = db.session.query(db.func.max(Block.orden)).filter_by(lesson_id=original.lesson_id).scalar() or 0

    new_block = Block(
        lesson_id=original.lesson_id,
        tipo=original.tipo,
        orden=max_order + 1,
        visible=original.visible,
        configuracion=json.loads(json.dumps(original.configuracion))
    )
    db.session.add(new_block)
    db.session.commit()

    return jsonify({
        'success': True,
        'block': {
            'id': new_block.id,
            'lesson_id': new_block.lesson_id,
            'tipo': new_block.tipo,
            'orden': new_block.orden,
            'visible': new_block.visible,
            'configuracion': new_block.configuracion
        }
    })


@learning_bp.route('/api/block/reorder', methods=['POST'])
@login_required
def api_reorder_blocks():
    block_ids = request.json.get('block_ids', [])
    for idx, b_id in enumerate(block_ids, 1):
        blk = Block.query.get(b_id)
        if blk:
            blk.orden = idx
    db.session.commit()
    return jsonify({'success': True})


@learning_bp.route('/api/upload', methods=['POST'])
@login_required
def api_upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        fname = f"media_{uuid.uuid4().hex}.{ext}"
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'learning')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, fname))

        url = url_for('static', filename=f"uploads/learning/{fname}")
        return jsonify({'success': True, 'url': url, 'filename': file.filename})

    return jsonify({'error': 'Tipo de archivo no permitido. Tipos válidos: jpg, png, webp, gif, mp4, webm, pdf, mp3'}), 400


# ==========================================
# VISTAS Y API ESTUDIANTE
# ==========================================

@learning_bp.route('/student/catalog')
@login_required
def student_catalog():
    learnings = Learning.query.filter_by(estado='published').order_by(Learning.fecha_creacion.desc()).all()
    user_progresses = {p.learning_id: p for p in LearningProgress.query.filter_by(user_id=current_user.id).all()}

    return render_template('learning/student_catalog.html', learnings=learnings, user_progresses=user_progresses)


@learning_bp.route('/student/view/<int:learning_id>')
@login_required
def student_view(learning_id):
    learning = Learning.query.get_or_404(learning_id)
    if learning.estado != 'published' and current_user.role not in ['instructor', 'admin', 'superuser']:
        flash('Esta capacitación aún no ha sido publicada.', 'warning')
        return redirect(url_for('learning.student_catalog'))

    progress = LearningProgress.query.filter_by(user_id=current_user.id, learning_id=learning_id).first()

    # Obtener respuestas de preguntas dadas por el estudiante
    block_answers = {
        ans.block_id: ans for ans in BlockAnswer.query.filter_by(user_id=current_user.id).all()
    }

    blocks_map = {
        les.id: [{
            "id": blk.id,
            "lesson_id": blk.lesson_id,
            "tipo": blk.tipo,
            "orden": blk.orden,
            "visible": blk.visible,
            "configuracion": blk.configuracion or {}
        } for blk in les.blocks]
        for mod in learning.modules for les in mod.lessons
    }

    return render_template('learning/student_view.html', learning=learning, progress=progress, block_answers=block_answers, blocks_map=blocks_map)



@learning_bp.route('/api/progress/update', methods=['POST'])
@login_required
def api_update_progress():
    data = request.json or {}
    learning_id = data.get('learning_id')
    lesson_id = data.get('lesson_id')
    block_id = data.get('block_id')
    time_delta = data.get('time_delta', 0)

    if not learning_id:
        return jsonify({'error': 'Missing learning_id'}), 400

    progress = learning_service.update_student_progress(
        user_id=current_user.id,
        learning_id=learning_id,
        lesson_id=lesson_id,
        block_id=block_id,
        time_delta=time_delta
    )

    return jsonify({
        'success': True,
        'progress_percent': progress.progress_percent,
        'completed': progress.completed,
        'score': progress.score,
        'time_spent': progress.time_spent_seconds
    })


@learning_bp.route('/api/block/submit-answer', methods=['POST'])
@login_required
def api_submit_block_answer():
    data = request.json or {}
    block_id = data.get('block_id')
    student_answer_data = data.get('answer', {})

    block = Block.query.get_or_404(block_id)
    result = learning_service.grade_question_block(block, student_answer_data)

    answer_rec = BlockAnswer.query.filter_by(user_id=current_user.id, block_id=block_id).first()
    if not answer_rec:
        answer_rec = BlockAnswer(
            user_id=current_user.id,
            block_id=block_id,
            answer_data=student_answer_data,
            is_correct=result['is_correct'],
            score=result['score']
        )
        db.session.add(answer_rec)
    else:
        answer_rec.answer_data = student_answer_data
        answer_rec.is_correct = result['is_correct']
        answer_rec.score = result['score']

    db.session.commit()

    # Actualizar progreso general de la capacitación
    lesson = block.lesson
    module = lesson.module
    learning_service.update_student_progress(
        user_id=current_user.id,
        learning_id=module.learning_id,
        lesson_id=lesson.id,
        block_id=block.id
    )

    # socketio event notification for real-time tracking if needed
    try:
        socketio.emit('student_learning_activity', {
            'user_id': current_user.id,
            'username': current_user.username,
            'learning_id': module.learning_id,
            'score': result['score'],
            'is_correct': result['is_correct']
        })
    except Exception:
        pass

    return jsonify({
        'success': True,
        'result': result
    })
