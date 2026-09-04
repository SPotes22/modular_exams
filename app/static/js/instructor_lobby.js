/* ═══════════════════════════════════════════════════════════════
   instructor_lobby.js
   Requiere que window.LOBBY_CONFIG esté definido antes de este
   script con: sessionId, roomCode, totalQuestions, isPaused,
   isRunning, examQuestions[]
═══════════════════════════════════════════════════════════════ */

const {
    sessionId,
    roomCode,
    totalQuestions,
    examQuestions = [],
} = window.LOBBY_CONFIG;

let isPaused = window.LOBBY_CONFIG.isPaused;

const socket = io();

/* ─────────────────────────────────────────────
   Conexión: emitir teacher_join para que el
   servidor registre al instructor y dispare
   students_updated con la lista actual.
   ───────────────────────────────────────────── */

socket.on('connect', () => {
    socket.emit('teacher_join', { room_code: roomCode });
});

/* ─────────────────────────────────────────────
   Control del examen
   ───────────────────────────────────────────── */

function startExam() {
    fetch(`/instructor/session/start-ajax/${sessionId}`, {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
    }).catch(err => console.error('Error al iniciar examen:', err));
}

function togglePause() {
    if (isPaused) {
        socket.emit('resume_exam', { room_code: roomCode });
    } else {
        socket.emit('pause_exam', { room_code: roomCode });
    }
}

function nextTeacherQuestion() {
    socket.emit('next_question', { room_code: roomCode });
}

/* ─────────────────────────────────────────────
   UI de estado: pausa / reanuda / iniciado
   ───────────────────────────────────────────── */

function applyPauseUI() {
    isPaused = true;

    const btn    = document.getElementById('btn-pause');
    const banner = document.getElementById('pause-banner');
    const badge  = document.getElementById('session-status-badge');
    const text   = document.getElementById('session-status-text');

    if (btn) {
        btn.innerHTML = '<i class="bi bi-play-circle-fill me-1"></i>Reanudar';
        btn.classList.replace('btn-warning', 'btn-success');
    }
    if (banner) banner.classList.remove('d-none');
    if (badge)  badge.style.background = '#f59e0b';
    if (text)   text.textContent = 'PAUSADO';
}

function applyResumeUI() {
    isPaused = false;

    const btn    = document.getElementById('btn-pause');
    const banner = document.getElementById('pause-banner');
    const badge  = document.getElementById('session-status-badge');
    const text   = document.getElementById('session-status-text');

    if (btn) {
        btn.innerHTML = '<i class="bi bi-pause-circle-fill me-1"></i>Pausar';
        btn.classList.replace('btn-success', 'btn-warning');
    }
    if (banner) banner.classList.add('d-none');
    if (badge)  badge.style.background = '#22c55e';
    if (text)   text.textContent = 'EN PROGRESO';
}

socket.on('exam_paused',  () => applyPauseUI());
socket.on('exam_resumed', () => applyResumeUI());

socket.on('exam_started', data => {
    const badge = document.getElementById('session-status-badge');
    const text  = document.getElementById('session-status-text');
    if (badge) badge.style.background = '#22c55e';
    if (text)  text.textContent = data.status || 'EN PROGRESO';

    document.getElementById('btn-start')?.classList.add('d-none');
    document.getElementById('btn-pause')?.classList.remove('d-none');
});

socket.on('teacher_can_continue', () => {
    document.getElementById('btn-next-question')?.classList.remove('d-none');
});
socket.on('next_question', () => {
    document.getElementById('btn-next-question')?.classList.add('d-none');
});

// Aplicar estado inicial según lo que llegó del servidor
if (window.LOBBY_CONFIG.isPaused) {
    applyPauseUI();
    document.getElementById('btn-pause')?.classList.remove('d-none');
}
if (window.LOBBY_CONFIG.isRunning) {
    document.getElementById('btn-start')?.classList.add('d-none');
    document.getElementById('btn-pause')?.classList.remove('d-none');
}

/* ─────────────────────────────────────────────
   Mapa de preguntas respondidas por alumno.
   Usamos Set<question_id> para no contar la
   misma pregunta más de una vez aunque el
   alumno navegue entre pestañas varias veces.
   ───────────────────────────────────────────── */

const _answeredSets = {}; // { student_id: Set<question_id> }

/* ─────────────────────────────────────────────
   Renderizado de estudiantes
   ───────────────────────────────────────────── */

socket.on('students_updated', data => {
    renderStudents(
        Array.isArray(data?.students) ? data.students : []
    );
});

socket.on('student_answered', data => {
    const sid = data.student_id;
    const qid = data.question_id;

    if (!_answeredSets[sid]) {
        _answeredSets[sid] = new Set();
    }
    // Set ignora duplicados: si ya estaba, el size no cambia
    _answeredSets[sid].add(qid);

    const answered = _answeredSets[sid].size; // nunca supera totalQuestions
    const badge = document.getElementById(`answered-badge-${sid}`);
    if (badge) {
        badge.textContent = `${Math.min(answered, totalQuestions)} / ${totalQuestions}`;
    }
});

function renderStudents(students) {
    const list  = document.getElementById('students-list');
    const count = document.getElementById('live-count');

    if (!list || !count) return;

    list.innerHTML = '';

    if (!students.length) {
        count.textContent = '0 en línea';
        list.innerHTML = `
            <li class="list-group-item text-muted text-center py-4">
                <i class="bi bi-person-slash fs-2 d-block mb-2"></i>
                Esperando a que los estudiantes se unan a la sala…
            </li>`;
        return;
    }

    const online = students.filter(s => s.connected).length;
    count.textContent = `${online} en línea`;
    students.forEach(student => list.appendChild(createStudentCard(student)));
}

function createStudentCard(student) {
    // Prioriza el Set local (más preciso) sobre answered_count del payload
    const fromSet = _answeredSets[student.id]
        ? _answeredSets[student.id].size
        : null;
    const answered = Math.min(
        fromSet !== null ? fromSet : (student.answered_count || 0),
        totalQuestions
    );
    const pct = totalQuestions
        ? Math.round(answered / totalQuestions * 100)
        : 0;

    const li = document.createElement('li');
    li.className = 'list-group-item py-3';
    li.innerHTML = `
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
            <div>
                <div class="fw-bold fs-6 text-dark d-flex align-items-center gap-2">
                    <i class="bi bi-person-circle text-primary"></i>
                    ${escapeHtml(student.username)}
                    <span class="badge ${student.connected ? 'bg-success' : 'bg-secondary'}">
                        ${student.connected ? 'Conectado' : 'Desconectado'}
                    </span>
                </div>
                <div class="small text-muted mt-1 d-flex align-items-center gap-3">
                    <span>Respondidas: <strong id="answered-badge-${student.id}">${answered} / ${totalQuestions}</strong></span>
                    <span>Puntaje: <strong>${Number(student.score || 0)} pts</strong></span>
                </div>
                <div class="progress mt-2" style="height:6px;width:200px;">
                    <div class="progress-bar bg-success" style="width:${pct}%;"></div>
                </div>
            </div>
            <button class="btn btn-outline-primary btn-sm shadow-sm" data-student-id="${student.id}">
                <i class="bi bi-list-check me-1"></i>Ver respuestas
            </button>
        </div>`;

    li.querySelector('button').addEventListener('click', () => showStudentDetails(student));
    return li;
}

/* ─────────────────────────────────────────────
   Modal detalle de respuestas del estudiante
   ───────────────────────────────────────────── */

function showStudentDetails(student) {
    document.getElementById('modalStudentName').textContent = student.username;

    const body    = document.getElementById('modalStudentDetailsBody');
    const answers = student.answered_questions || {};
    body.innerHTML = '';

    examQuestions.forEach((q, idx) => {
        const qAns = answers[q.id] || answers[String(q.id)];

        let badge   = '<span class="badge bg-secondary py-2 px-3"><i class="bi bi-dash-circle me-1"></i>Sin responder</span>';
        let ansText = '<em class="text-muted">Aún no respondida.</em>';

        if (qAns) {
            const correct = qAns.result?.correct;
            badge = correct
                ? '<span class="badge bg-success py-2 px-3"><i class="bi bi-check-circle-fill me-1"></i>Correcta</span>'
                : '<span class="badge bg-danger py-2 px-3"><i class="bi bi-x-circle-fill me-1"></i>Incorrecta</span>';

            const raw = qAns.result?.selected_option_text
                || qAns.answer?.text
                || (qAns.answer?.selected_option_id ? `opción ID ${qAns.answer.selected_option_id}` : null)
                || 'Respuesta registrada';

            ansText = `<strong>Respuesta:</strong>
                <span class="badge bg-white text-dark border px-2 py-1 ms-1">${escapeHtml(raw)}</span>`;
        }

        const card = document.createElement('div');
        card.className = 'card mb-3 border-0 shadow-sm';
        card.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="fw-bold mb-0 text-dark">${idx + 1}. ${escapeHtml(q.statement)}</h6>
                    <div>${badge}</div>
                </div>
                <div class="small text-secondary">${ansText}</div>
            </div>`;
        body.appendChild(card);
    });

    new bootstrap.Modal(document.getElementById('studentDetailModal')).show();
}

/* ─────────────────────────────────────────────
   Anti-cheat
   ───────────────────────────────────────────── */

socket.on('cheat_warning', data => {
    const log = document.getElementById('alerts-log');
    document.getElementById('no-alerts')?.remove();

    const div = document.createElement('div');
    div.className = 'alert alert-warning border-0 shadow-sm py-2 px-3 mb-2 small';
    div.innerHTML = `<i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>
        <strong>${escapeHtml(data.username)}</strong>: ${escapeHtml(data.reason)}`;
    log.prepend(div);
});

/* ─────────────────────────────────────────────
   Utilidades
   ───────────────────────────────────────────── */

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g,  '&amp;')
        .replace(/</g,  '&lt;')
        .replace(/>/g,  '&gt;')
        .replace(/"/g,  '&quot;')
        .replace(/'/g,  '&#039;');
}
