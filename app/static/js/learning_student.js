// app/static/js/learning_student.js

let studentLessonId = window.INITIAL_LESSON_ID;
let timeSpentSeconds = window.INITIAL_TIME_SPENT || 0;
let timerInterval = null;
let allLessonsList = [];

document.addEventListener('DOMContentLoaded', () => {
    // Recopilar lista de lecciones para navegación Siguiente/Anterior
    document.querySelectorAll('.student-lesson-btn').forEach(btn => {
        allLessonsList.push({
            id: parseInt(btn.getAttribute('data-lesson-id')),
            title: btn.getAttribute('data-lesson-title'),
            element: btn
        });
    });

    if (studentLessonId) {
        const activeBtn = allLessonsList.find(l => l.id === studentLessonId);
        if (activeBtn) {
            loadStudentLesson(studentLessonId, activeBtn.element);
        } else if (allLessonsList.length > 0) {
            loadStudentLesson(allLessonsList[0].id, allLessonsList[0].element);
        }
    }

    startProgressTimer();
});

function startProgressTimer() {
    timerInterval = setInterval(() => {
        timeSpentSeconds++;
        updateTimerDisplay();

        // Guardar progreso cada 15 segundos
        if (timeSpentSeconds % 15 === 0) {
            saveProgressToBackend(0);
        }
    }, 1000);
}

function updateTimerDisplay() {
    const mins = Math.floor(timeSpentSeconds / 60);
    const secs = timeSpentSeconds % 60;
    const timerText = document.getElementById('timerText');
    if (timerText) timerText.textContent = `${mins}m ${secs}s`;
}

function loadStudentLesson(lessonId, btnElement) {
    document.querySelectorAll('.student-lesson-btn').forEach(btn => btn.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');

    studentLessonId = lessonId;
    const item = allLessonsList.find(l => l.id === lessonId);
    if (item) {
        document.getElementById('studentLessonTitle').textContent = item.title;
    }

    // Actualizar progreso
    saveProgressToBackend(1);

    // Cargar bloques desde la API o DOM
    fetchLessonBlocks(lessonId);
}

function fetchLessonBlocks(lessonId) {
    const container = document.getElementById('studentBlocksContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-2 text-muted">Cargando bloques de la lección...</p>
        </div>
    `;

    fetch(`/learning/instructor/builder/${window.LEARNING_ID}`)
    .then(() => {
        // En un entorno de producción, obtenemos los bloques de la lección seleccionada
        if (!window.LESSON_BLOCKS_MAP) window.LESSON_BLOCKS_MAP = {};
        const blocks = window.LESSON_BLOCKS_MAP[lessonId] || [];
        renderStudentBlocks(blocks);
    });
}

function renderStudentBlocks(blocks) {
    const container = document.getElementById('studentBlocksContainer');
    if (!container) return;

    const visibleBlocks = blocks.filter(b => b.visible);
    if (visibleBlocks.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info text-center py-4">
                <i class="bi bi-info-circle display-4 d-block mb-2"></i>
                Esta lección no contiene bloques de contenido aún.
            </div>
        `;
        return;
    }

    let html = '';
    visibleBlocks.forEach(blk => {
        html += `
            <div class="block-student-item mb-4 pb-3 border-bottom" id="block_${blk.id}">
                ${renderStudentBlockContent(blk)}
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderStudentBlockContent(blk) {
    const cfg = blk.configuracion || {};

    if (blk.tipo === 'title') {
        const level = cfg.level || 'h2';
        return `<${level} class="fw-bold text-primary mb-2">${cfg.title || ''}</${level}>
                ${cfg.subtitle ? `<p class="text-muted fs-5 mb-0">${cfg.subtitle}</p>` : ''}`;
    }

    if (blk.tipo === 'text') {
        return `<div class="fs-6 lh-lg">${cfg.content || ''}</div>`;
    }

    if (blk.tipo === 'image') {
        if (!cfg.src) return '';
        return `
            <div class="text-${cfg.alignment || 'center'} my-3">
                <img src="${cfg.src}" class="img-fluid rounded shadow-sm" style="max-height: 500px;" alt="${cfg.alt || ''}" loading="lazy">
                ${cfg.caption ? `<p class="text-muted small mt-2 italic">${cfg.caption}</p>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'video') {
        if (!cfg.url) return '';
        if (cfg.url.includes('youtube.com') || cfg.url.includes('youtu.be')) {
            let embedUrl = cfg.url;
            if (cfg.url.includes('watch?v=')) embedUrl = cfg.url.replace('watch?v=', 'embed/');
            return `
                <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm my-3">
                    <iframe src="${embedUrl}" allowfullscreen loading="lazy"></iframe>
                </div>
                ${cfg.caption ? `<p class="text-muted small mt-2">${cfg.caption}</p>` : ''}
            `;
        }
        return `
            <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm my-3">
                <video controls ${cfg.autoplay ? 'autoplay' : ''}>
                    <source src="${cfg.url}" type="video/mp4">
                </video>
            </div>
            ${cfg.caption ? `<p class="text-muted small mt-2">${cfg.caption}</p>` : ''}
        `;
    }

    if (blk.tipo === 'question') {
        return renderQuestionBlockStudent(blk);
    }

    if (blk.tipo === 'divider') {
        return `<hr class="my-4 border-${cfg.style || 'solid'}">`;
    }

    if (blk.tipo === 'quote') {
        const styleClass = cfg.style === 'warning' ? 'alert-warning' : cfg.style === 'note' ? 'alert-info' : 'bg-light border-start border-4 border-primary p-3';
        return `
            <div class="${styleClass} rounded my-3">
                <blockquote class="blockquote mb-1 fs-5">
                    <p class="mb-1">${cfg.text || ''}</p>
                </blockquote>
                ${cfg.author ? `<figcaption class="blockquote-footer mb-0 mt-1">${cfg.author}</figcaption>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'pdf') {
        if (!cfg.src) return '';
        return `
            <div class="border rounded p-3 text-center bg-light my-3">
                <h6 class="fw-bold mb-3"><i class="bi bi-file-earmark-pdf text-danger me-2"></i>${cfg.title || 'Documento PDF'}</h6>
                <div class="ratio ratio-16x9 mb-3">
                    <iframe src="${cfg.src}"></iframe>
                </div>
                ${cfg.downloadable ? `<a href="${cfg.src}" download class="btn btn-sm btn-outline-danger"><i class="bi bi-download me-1"></i>Descargar PDF</a>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'download') {
        return `
            <div class="d-flex align-items-center justify-content-between p-3 border rounded bg-light my-3">
                <div>
                    <h6 class="fw-bold mb-1"><i class="bi bi-paperclip me-2 text-primary"></i>${cfg.title || 'Recurso Descargable'}</h6>
                    <small class="text-muted">${cfg.description || ''}</small>
                </div>
                ${cfg.src ? `<a href="${cfg.src}" download="${cfg.filename || 'archivo'}" class="btn btn-success btn-sm"><i class="bi bi-download me-1"></i>Descargar</a>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'audio') {
        return `
            <div class="p-3 border rounded bg-light my-3">
                <h6 class="fw-bold mb-2"><i class="bi bi-music-note-beamer text-primary me-2"></i>${cfg.title || 'Audio'} ${cfg.author ? `(${cfg.author})` : ''}</h6>
                ${cfg.src ? `<audio controls class="w-100"><source src="${cfg.src}"></audio>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'embed') {
        if (cfg.iframe_code) {
            return `<div class="embed-responsive shadow-sm rounded overflow-hidden my-3">${cfg.iframe_code}</div>`;
        }
        if (cfg.url) {
            return `
                <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm my-3">
                    <iframe src="${cfg.url}" allowfullscreen loading="lazy"></iframe>
                </div>
            `;
        }
    }

    return '';
}

function renderQuestionBlockStudent(blk) {
    const cfg = blk.configuracion || {};
    const qtype = cfg.question_type || 'single_choice';

    let inputHtml = '';
    if (qtype === 'single_choice' || qtype === 'multiple_choice') {
        const inputType = qtype === 'single_choice' ? 'radio' : 'checkbox';
        const opts = cfg.options || [];
        opts.forEach(opt => {
            inputHtml += `
                <div class="form-check mb-2">
                    <input class="form-check-input" type="${inputType}" name="q_${blk.id}" value="${opt.id}" id="q_${blk.id}_opt_${opt.id}">
                    <label class="form-check-label fw-semibold" for="q_${blk.id}_opt_${opt.id}">${opt.text}</label>
                </div>
            `;
        });
    } else if (qtype === 'true_false') {
        inputHtml = `
            <div class="form-check mb-2">
                <input class="form-check-input" type="radio" name="q_${blk.id}" value="true" id="q_${blk.id}_t">
                <label class="form-check-label fw-semibold" for="q_${blk.id}_t">Verdadero</label>
            </div>
            <div class="form-check mb-2">
                <input class="form-check-input" type="radio" name="q_${blk.id}" value="false" id="q_${blk.id}_f">
                <label class="form-check-label fw-semibold" for="q_${blk.id}_f">Falso</label>
            </div>
        `;
    } else if (qtype === 'short_answer') {
        inputHtml = `
            <div class="mb-3">
                <input type="text" class="form-control" id="q_${blk.id}_text" placeholder="Escribe tu respuesta aquí...">
            </div>
        `;
    }

    return `
        <div class="card border-warning shadow-sm my-3">
            <div class="card-header bg-warning bg-opacity-10 d-flex justify-content-between align-items-center fw-bold">
                <span><i class="bi bi-question-circle-fill text-warning me-2"></i>Pregunta Interactiva</span>
                <span class="badge bg-warning text-dark">${cfg.points || 10} Pts</span>
            </div>
            <div class="card-body">
                <h5 class="fw-bold mb-3">${cfg.question || ''}</h5>
                <form id="form_q_${blk.id}">
                    ${inputHtml}
                    <div class="mt-3">
                        <button type="button" class="btn btn-primary btn-sm px-4 fw-bold" onclick="submitBlockAnswer(${blk.id}, '${qtype}')">
                            <i class="bi bi-send me-1"></i>Responder
                        </button>
                    </div>
                </form>
                <div class="mt-3 d-none" id="feedback_q_${blk.id}"></div>
            </div>
        </div>
    `;
}

function submitBlockAnswer(blockId, qtype) {
    let answerData = {};

    if (qtype === 'single_choice') {
        const selected = document.querySelector(`input[name="q_${blockId}"]:checked`);
        if (!selected) {
            alert('Por favor selecciona una opción.');
            return;
        }
        answerData.selected_options = [selected.value];
    } else if (qtype === 'multiple_choice') {
        const checked = document.querySelectorAll(`input[name="q_${blockId}"]:checked`);
        if (checked.length === 0) {
            alert('Por favor selecciona al menos una opción.');
            return;
        }
        answerData.selected_options = Array.from(checked).map(c => c.value);
    } else if (qtype === 'true_false') {
        const selected = document.querySelector(`input[name="q_${blockId}"]:checked`);
        if (!selected) {
            alert('Por favor selecciona Verdadero o Falso.');
            return;
        }
        answerData.true_false_val = selected.value === 'true';
    } else if (qtype === 'short_answer') {
        const val = document.getElementById(`q_${blockId}_text`)?.value;
        if (!val || !val.trim()) {
            alert('Por favor escribe una respuesta.');
            return;
        }
        answerData.text_response = val;
    }

    fetch('/learning/api/block/submit-answer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            block_id: blockId,
            answer: answerData
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const res = data.result;
            const fbContainer = document.getElementById(`feedback_q_${blockId}`);
            if (fbContainer) {
                fbContainer.classList.remove('d-none');
                const alertClass = res.is_correct ? 'alert-success' : 'alert-danger';
                const icon = res.is_correct ? 'bi-check-circle-fill' : 'bi-x-circle-fill';
                fbContainer.innerHTML = `
                    <div class="alert ${alertClass} mb-0">
                        <h6 class="fw-bold mb-1"><i class="bi ${icon} me-1"></i>${res.is_correct ? '¡Respuesta Correcta!' : 'Respuesta Incorrecta'} (${res.score} / ${res.max_points} Pts)</h6>
                        ${res.feedback ? `<p class="mb-1 small">${res.feedback}</p>` : ''}
                        ${res.explanation ? `<p class="mb-0 small text-muted"><strong>Explicación:</strong> ${res.explanation}</p>` : ''}
                    </div>
                `;
            }
        }
    });
}

function navigateLesson(direction) {
    const idx = allLessonsList.findIndex(l => l.id === studentLessonId);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx >= 0 && newIdx < allLessonsList.length) {
        const nextLes = allLessonsList[newIdx];
        loadStudentLesson(nextLes.id, nextLes.element);
    }
}

function saveProgressToBackend(timeDelta) {
    // Si la lección o la capacitación aún no se han seleccionado/cargado, no hacer nada
    if (!studentLessonId || !window.LEARNING_ID) {
        return;
    }

    fetch('/learning/api/progress/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            learning_id: window.LEARNING_ID,
            lesson_id: studentLessonId,
            time_delta: timeDelta
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const pBar = document.getElementById('progressBar');
            const pText = document.getElementById('progressPercentText');
            const sText = document.getElementById('scoreText');

            if (pBar) pBar.style.width = `${data.progress_percent}%`;
            if (pText) pText.textContent = `${data.progress_percent.toFixed(1)}%`;
            if (sText) sText.textContent = `${data.score.toFixed(1)} Pts`;
        }
    })
    .catch(err => console.error("Error guardando progreso:", err));
}
    
    fetch('/learning/api/progress/update', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            learning_id: window.LEARNING_ID,
            lesson_id: studentLessonId,
            time_delta: timeDelta
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const pBar = document.getElementById('progressBar');
            const pText = document.getElementById('progressPercentText');
            const sText = document.getElementById('scoreText');

            if (pBar) pBar.style.width = `${data.progress_percent}%`;
            if (pText) pText.textContent = `${data.progress_percent.toFixed(1)}%`;
            if (sText) sText.textContent = `${data.score.toFixed(1)} Pts`;
        }
    });
}
