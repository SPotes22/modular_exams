# Módulo de exámenes estilo Socrative

## Auditoría de arquitectura reutilizada

- **Persistencia**: se mantiene Flask-SQLAlchemy con los modelos centrales `User`, `Bank`, `Question`, `QuestionOption`, `QuestionMatching`, `QuestionOrder`, `Exam`, `ExamQuestion`, `ExamSession`, `ExamAttempt` y `StudentAnswer`.
- **Blueprints**: se reutilizan `questions_bp` para banco de preguntas, `exams_bp` para biblioteca/constructor/salas/resultados, `learning_bp` para capacitaciones, `auth_bp` para login y `media_bp` para servir multimedia.
- **Realtime**: se conserva `app/realtime` y Socket.IO; no se agregó otro sistema de sockets. Los controles nuevos emiten `exam_started`, `exam_paused`, `exam_resumed` y `exam_finished` sobre la sala existente.
- **Multimedia**: las preguntas mantienen `image_url`, `video_url` y la convención de rutas bajo `app/static/uploads`.
- **Excel**: se conserva `pandas`/`openpyxl`, que ya estaba declarado en `requirements.txt`.

## Modelos y relaciones nuevas o extendidas

- `Question.default_points`: puntaje por defecto de la pregunta en el banco.
- `ExamQuestion.order_index`: orden persistente en el constructor.
- `ExamQuestion.points`: puntaje por pregunta dentro de cada examen; permite que una misma pregunta valga distinto en exámenes diferentes.
- `Exam.instructions`, `Exam.status`, `Exam.allow_multiple_attempts`, `Exam.max_attempts`, `Exam.created_at`, `Exam.updated_at`.
- `ExamSession.question_order`: `original` o `random` al crear una sala.
- `ExamAttempt.attempt_number`, `earned_points`, `max_points`.
- `StudentAnswer.answer_text`, `points_awarded`.
- `ExamClass`: clases/asignaturas del profesor, relacionadas a exámenes sin duplicarlos físicamente.
- `ExamGroup`: agrupación lógica para biblioteca de exámenes.
- `User.default_exam_view`: preferencia de pantalla inicial.

`ensure_schema()` agrega columnas faltantes de forma compatible con bases SQLite existentes creadas previamente por `db.create_all()`.

## Rutas principales

### Preguntas

- `GET /instructor/mis-preguntas`: banco de preguntas con búsqueda, filtro por banco y filtro por tipo.
- `POST /instructor/question/create`: crea preguntas individuales.
- `POST /instructor/question/edit/<question_id>`: edita texto, tipo, opciones, respuestas, feedback, imagen y puntos.
- `POST /instructor/question/duplicate/<question_id>`: duplica una pregunta del banco.
- `POST /instructor/question/delete/<question_id>`: elimina la pregunta global del banco.

### Exámenes

- `GET /instructor/exams`: biblioteca de exámenes.
- `GET|POST /instructor/exam/new`: crea un examen vacío.
- `GET|POST /instructor/exam/<exam_id>/edit`: constructor único del examen.
- `POST /instructor/exam/<exam_id>/add-bank`: agrega preguntas existentes o aleatorias sin duplicados.
- `POST /instructor/exam/<exam_id>/question/create`: crea una pregunta desde el constructor y la agrega automáticamente.
- `POST /instructor/exam/<exam_id>/question/<question_id>/<action>`: acciones `remove`, `duplicate`, `up`, `down`.
- `POST /instructor/exam/<exam_id>/duplicate`: duplica el examen.
- `POST /instructor/exam/<exam_id>/delete`: elimina el examen.
- `GET /instructor/exam/<exam_id>/export/with-answers`: exportación imprimible con respuestas.
- `GET /instructor/exam/<exam_id>/export/without-answers`: exportación imprimible sin respuestas.

### Clases, sesiones, historial y resultados

- `GET|POST /instructor/classes`: gestiona clases.
- `POST /instructor/class/<class_id>/assign`: asigna examen a clase por relación.
- `GET|POST /instructor/session/configure/<exam_id>`: configura orden original/aleatorio y crea sala.
- `POST /instructor/session/<session_id>/start|pause|resume|finish`: controla la sala y sincroniza eventos realtime.
- `GET /instructor/history`: historial de presentaciones.
- `GET /instructor/results`: resultados filtrables por asignatura.
- `GET /instructor/session/<session_id>/results.xlsx`: exportación XLS de resultados existente.

## Validaciones y permisos

- El backend valida propiedad del profesor antes de editar preguntas, exámenes, clases, sesiones y resultados.
- La retroalimentación tiene límite estricto de 3000 caracteres en frontend (`maxlength`) y backend.
- Los puntos deben ser numéricos y mayores que cero.
- La selección aleatoria rechaza cantidades mayores a las preguntas disponibles sin duplicados.
- Una sala pausada bloquea el envío HTTP tradicional.
- Los intentos respetan `allow_multiple_attempts` y `max_attempts`.
- La exportación sin respuestas renderiza el examen sin `is_correct`, `correct_answer` ni identificadores de respuesta correcta visibles.

## Nota sobre `run.py`

Se aplicó un cambio mínimo para permitir que Flask-SocketIO arranque con Werkzeug en este entorno de desarrollo moderno. No cambia la arquitectura ni el despliegue recomendado; en producción debe usarse un servidor WSGI/ASGI apropiado.
