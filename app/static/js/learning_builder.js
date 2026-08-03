// app/static/js/learning_builder.js

let currentLessonId = window.INITIAL_LESSON_ID;
let currentBlocks = [];
let editingBlockId = null;
let isPreviewMode = false;

document.addEventListener('DOMContentLoaded', () => {
    if (currentLessonId) {
        loadLessonBlocks(currentLessonId);
    }

    // Toggle modo edición / preview
    document.getElementById('btnEditMode')?.addEventListener('click', () => setPreviewMode(false));
    document.getElementById('btnPreviewMode')?.addEventListener('click', () => setPreviewMode(true));

    // Toggle publicación
    const btnPub = document.getElementById('btnPublishToggle');
    if (btnPub) {
        btnPub.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            fetch(`/learning/instructor/toggle-publish/${id}`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if(data.success) {
                    const pubText = document.getElementById('pubText');
                    if(data.nuevo_estado === 'published') {
                        this.className = 'btn btn-sm btn-success';
                        if(pubText) pubText.textContent = 'Publicado';
                    } else {
                        this.className = 'btn btn-sm btn-warning text-dark';
                        if(pubText) pubText.textContent = 'Borrador';
                    }
                }
            });
        });
    }
});

function setPreviewMode(preview) {
    isPreviewMode = preview;
    const btnEdit = document.getElementById('btnEditMode');
    const btnPrev = document.getElementById('btnPreviewMode');
    
    if (preview) {
        btnEdit.className = 'btn btn-sm btn-outline-primary';
        btnPrev.className = 'btn btn-sm btn-primary active';
    } else {
        btnEdit.className = 'btn btn-sm btn-primary active';
        btnPrev.className = 'btn btn-sm btn-outline-primary';
    }
    renderBlocks();
}

function selectLesson(lessonId, btnElement) {
    document.querySelectorAll('.lesson-nav-btn').forEach(btn => btn.classList.remove('active'));
    if(btnElement) btnElement.classList.add('active');

    const title = btnElement ? btnElement.getAttribute('data-lesson-title') : 'Lección';
    document.getElementById('currentLessonHeader').textContent = title;

    currentLessonId = lessonId;
    loadLessonBlocks(lessonId);
}

function loadLessonBlocks(lessonId) {
    // Buscar bloques de la lección seleccionada
    fetch(`/learning/student/view/${window.LEARNING_ID}`)
    .then(r => r.text())
    .then(() => {
        // Obtenemos bloques via fetch de actualización o extracción
        fetchBlocksFromBackend(lessonId);
    });
}

function fetchBlocksFromBackend(lessonId) {
    // Si no hay endpoint JSON directo de lección, podemos consultar la lista de bloques
    fetch(`/learning/instructor/builder/${window.LEARNING_ID}`)
    .then(() => {
        // render initial empty or current blocks
        if (!window.LESSON_BLOCKS_MAP) window.LESSON_BLOCKS_MAP = {};
        currentBlocks = window.LESSON_BLOCKS_MAP[lessonId] || [];
        renderBlocks();
    });
}

function renderBlocks() {
    const container = document.getElementById('blocksContainer');
    if (!container) return;

    if (!currentLessonId) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="bi bi-arrow-left-circle display-4"></i>
                <p class="mt-2">Selecciona o crea una lección en el panel izquierdo.</p>
            </div>
        `;
        return;
    }

    if (currentBlocks.length === 0) {
        container.innerHTML = `
            <div class="text-center py-5 text-muted border border-dashed rounded">
                <i class="bi bi-plus-circle-dotted display-4"></i>
                <h5 class="mt-2">Esta lección aún no tiene bloques</h5>
                <p>Agrega contenido enriquecido, videos, imágenes o preguntas interactivas.</p>
                <button class="btn btn-primary btn-sm" onclick="openAddBlockModal()">
                    <i class="bi bi-plus-circle me-1"></i>Agregar Primer Bloque
                </button>
            </div>
        `;
        return;
    }

    let html = '';
    currentBlocks.forEach((blk, idx) => {
        const isHiddenClass = (!blk.visible && !isPreviewMode) ? 'opacity-50 border-warning' : '';
        if (!blk.visible && isPreviewMode) return; // oculto en vista previa

        html += `
            <div class="block-wrapper card mb-3 shadow-sm border ${isHiddenClass}" data-block-id="${blk.id}" data-index="${idx}">
                ${!isPreviewMode ? `
                    <div class="card-header bg-light d-flex justify-content-between align-items-center py-1 px-3">
                        <small class="fw-bold text-uppercase text-secondary">
                            <i class="${getBlockIcon(blk.tipo)} me-1"></i>${getBlockTypeName(blk.tipo)} ${!blk.visible ? '(Oculto)' : ''}
                        </small>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-link text-dark p-0 me-2" onclick="moveBlock(${blk.id}, -1)" ${idx === 0 ? 'disabled' : ''} title="Mover arriba"><i class="bi bi-arrow-up"></i></button>
                            <button class="btn btn-link text-dark p-0 me-2" onclick="moveBlock(${blk.id}, 1)" ${idx === currentBlocks.length - 1 ? 'disabled' : ''} title="Mover abajo"><i class="bi bi-arrow-down"></i></button>
                            <button class="btn btn-link text-primary p-0 me-2" onclick="openBlockConfigModal(${blk.id})" title="Editar Configuración"><i class="bi bi-gear"></i></button>
                            <button class="btn btn-link text-secondary p-0 me-2" onclick="toggleBlockVisibility(${blk.id})" title="Visibilidad"><i class="bi ${blk.visible ? 'bi-eye' : 'bi-eye-slash'}"></i></button>
                            <button class="btn btn-link text-info p-0 me-2" onclick="duplicateBlock(${blk.id})" title="Duplicar"><i class="bi bi-copy"></i></button>
                            <button class="btn btn-link text-danger p-0" onclick="deleteBlock(${blk.id})" title="Eliminar"><i class="bi bi-trash"></i></button>
                        </div>
                    </div>
                ` : ''}
                <div class="card-body p-3">
                    ${renderBlockContent(blk)}
                </div>
            </div>
        `;
    });

    if (!isPreviewMode) {
        html += `
            <div class="text-center my-4">
                <button class="btn btn-outline-primary btn-sm rounded-pill px-4" onclick="openAddBlockModal()">
                    <i class="bi bi-plus-lg me-1"></i>Agregar Bloque Aquí
                </button>
            </div>
        `;
    }

    container.innerHTML = html;
}

function getBlockIcon(tipo) {
    const icons = {
        text: 'bi-file-richtext',
        image: 'bi-image',
        video: 'bi-play-btn',
        question: 'bi-patch-question',
        divider: 'bi-hr',
        title: 'bi-type-h1',
        quote: 'bi-quote',
        pdf: 'bi-file-earmark-pdf',
        download: 'bi-cloud-arrow-down',
        audio: 'bi-music-note-beamer',
        embed: 'bi-code-slash'
    };
    return icons[tipo] || 'bi-square';
}

function getBlockTypeName(tipo) {
    const names = {
        text: 'Texto Enriquecido',
        image: 'Imagen',
        video: 'Video',
        question: 'Pregunta',
        divider: 'Separador',
        title: 'Título / Encabezado',
        quote: 'Cita / Nota',
        pdf: 'Visor PDF',
        download: 'Descarga de Archivo',
        audio: 'Audio / Podcast',
        embed: 'Contenido Embebido'
    };
    return names[tipo] || tipo;
}

function renderBlockContent(blk) {
    const cfg = blk.configuracion || {};

    if (blk.tipo === 'title') {
        const level = cfg.level || 'h2';
        return `<${level} class="fw-bold mb-1">${cfg.title || 'Título'}</${level}>
                ${cfg.subtitle ? `<p class="text-muted mb-0">${cfg.subtitle}</p>` : ''}`;
    }

    if (blk.tipo === 'text') {
        return `<div class="rich-text-content">${cfg.content || '<p class="text-muted">Texto vacío...</p>'}</div>`;
    }

    if (blk.tipo === 'image') {
        if (!cfg.src) return `<div class="alert alert-light border text-center mb-0"><i class="bi bi-image me-1"></i>Sin imagen configurada. Haz clic en el icono de engranaje <i class="bi bi-gear"></i> para subir una imagen.</div>`;
        return `
            <div class="text-${cfg.alignment || 'center'}">
                <img src="${cfg.src}" class="img-fluid rounded shadow-sm" style="max-height: 400px;" alt="${cfg.alt || ''}" loading="lazy">
                ${cfg.caption ? `<p class="text-muted small mt-2 italic">${cfg.caption}</p>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'video') {
        if (!cfg.url) return `<div class="alert alert-light border text-center mb-0"><i class="bi bi-play-btn me-1"></i>Sin video configurado. Haz clic en el icono de engranaje <i class="bi bi-gear"></i> para añadir la URL del video.</div>`;
        if (cfg.url.includes('youtube.com') || cfg.url.includes('youtu.be')) {
            let embedUrl = cfg.url;
            if (cfg.url.includes('watch?v=')) embedUrl = cfg.url.replace('watch?v=', 'embed/');
            return `
                <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm">
                    <iframe src="${embedUrl}" allowfullscreen></iframe>
                </div>
                ${cfg.caption ? `<p class="text-muted small mt-2">${cfg.caption}</p>` : ''}
            `;
        }
        return `
            <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm">
                <video controls ${cfg.autoplay ? 'autoplay' : ''}>
                    <source src="${cfg.url}" type="video/mp4">
                    Tu navegador no soporta reproducción de video.
                </video>
            </div>
            ${cfg.caption ? `<p class="text-muted small mt-2">${cfg.caption}</p>` : ''}
        `;
    }

    if (blk.tipo === 'question') {
        const qtype = cfg.question_type || 'single_choice';
        return `
            <div class="p-3 border rounded bg-light">
                <div class="d-flex justify-content-between mb-2">
                    <span class="badge bg-warning text-dark text-uppercase">${qtype.replace('_', ' ')}</span>
                    <span class="fw-bold text-primary">${cfg.points || 10} Pts</span>
                </div>
                <h6 class="fw-bold mb-3">${cfg.question || '¿Pregunta?'}</h6>
                <div class="small text-muted mb-2">Responde en el panel interactivo del estudiante.</div>
            </div>
        `;
    }

    if (blk.tipo === 'divider') {
        return `<hr class="my-3 border-${cfg.style || 'solid'}">`;
    }

    if (blk.tipo === 'quote') {
        const styleClass = cfg.style === 'warning' ? 'alert-warning' : cfg.style === 'note' ? 'alert-info' : 'bg-light border-start border-4 border-primary p-3';
        return `
            <div class="${styleClass} rounded">
                <blockquote class="blockquote mb-1 fs-6">
                    <p class="mb-1">${cfg.text || 'Cita o nota'}</p>
                </blockquote>
                ${cfg.author ? `<figcaption class="blockquote-footer mb-0 mt-1">${cfg.author}</figcaption>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'pdf') {
        if (!cfg.src) return `<div class="alert alert-light border text-center mb-0"><i class="bi bi-file-earmark-pdf me-1"></i>Sin archivo PDF configurado.</div>`;
        return `
            <div class="border rounded p-3 text-center bg-light">
                <h6 class="fw-bold mb-2"><i class="bi bi-file-earmark-pdf text-danger me-2"></i>${cfg.title || 'Documento PDF'}</h6>
                <div class="ratio ratio-16x9 mb-2">
                    <iframe src="${cfg.src}"></iframe>
                </div>
                ${cfg.downloadable ? `<a href="${cfg.src}" download class="btn btn-sm btn-outline-danger"><i class="bi bi-download me-1"></i>Descargar PDF</a>` : ''}
            </div>
        `;
    }

    if (blk.tipo === 'download') {
        return `
            <div class="d-flex align-items-center justify-content-between p-3 border rounded bg-light">
                <div>
                    <h6 class="fw-bold mb-1"><i class="bi bi-paperclip me-2 text-primary"></i>${cfg.title || 'Recurso Descargable'}</h6>
                    <small class="text-muted">${cfg.description || ''}</small>
                </div>
                ${cfg.src ? `<a href="${cfg.src}" download="${cfg.filename || 'archivo'}" class="btn btn-success btn-sm"><i class="bi bi-download me-1"></i>Descargar</a>` : '<span class="badge bg-secondary">Sin archivo</span>'}
            </div>
        `;
    }

    if (blk.tipo === 'audio') {
        return `
            <div class="p-3 border rounded bg-light">
                <h6 class="fw-bold mb-2"><i class="bi bi-music-note-beamer text-primary me-2"></i>${cfg.title || 'Audio'} ${cfg.author ? `(${cfg.author})` : ''}</h6>
                ${cfg.src ? `<audio controls class="w-100"><source src="${cfg.src}">Tu navegador no soporta el reproductor de audio.</audio>` : '<div class="small text-muted">Sin archivo de audio cargado.</div>'}
            </div>
        `;
    }

    if (blk.tipo === 'embed') {
        if (!cfg.url && !cfg.iframe_code) return `<div class="alert alert-light border text-center mb-0"><i class="bi bi-code-slash me-1"></i>Sin contenido embebido configurado.</div>`;
        if (cfg.iframe_code) {
            return `<div class="embed-responsive shadow-sm rounded overflow-hidden">${cfg.iframe_code}</div>`;
        }
        return `
            <div class="ratio ratio-16x9 rounded overflow-hidden shadow-sm">
                <iframe src="${cfg.url}" allowfullscreen></iframe>
            </div>
        `;
    }

    return `<div class="text-muted">Bloque sin vista previa.</div>`;
}

function openAddBlockModal() {
    if (!currentLessonId) {
        alert('Debes seleccionar o crear una lección primero.');
        return;
    }
    const modal = new bootstrap.Modal(document.getElementById('addBlockModal'));
    modal.show();
}

function addBlock(tipo) {
    const modalEl = document.getElementById('addBlockModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if(modal) modal.hide();

    showSaving();
    const formData = new FormData();
    formData.append('lesson_id', currentLessonId);
    formData.append('tipo', tipo);

    fetch('/learning/api/block/create', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        showSaved();
        if (data.success) {
            currentBlocks.push(data.block);
            renderBlocks();
        }
    });
}

function moveBlock(blockId, direction) {
    const idx = currentBlocks.findIndex(b => b.id === blockId);
    if (idx < 0) return;
    const newIdx = idx + direction;
    if (newIdx < 0 || newIdx >= currentBlocks.length) return;

    // Swap elements locally
    const temp = currentBlocks[idx];
    currentBlocks[idx] = currentBlocks[newIdx];
    currentBlocks[newIdx] = temp;

    renderBlocks();

    // Send new order to backend
    showSaving();
    const blockIds = currentBlocks.map(b => b.id);
    fetch('/learning/api/block/reorder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ block_ids: blockIds })
    })
    .then(r => r.json())
    .then(() => showSaved());
}

function toggleBlockVisibility(blockId) {
    const blk = currentBlocks.find(b => b.id === blockId);
    if (!blk) return;

    blk.visible = !blk.visible;
    renderBlocks();

    showSaving();
    const formData = new FormData();
    formData.append('visible', blk.visible);

    fetch(`/learning/api/block/update/${blockId}`, { method: 'POST', body: formData })
    .then(r => r.json())
    .then(() => showSaved());
}

function duplicateBlock(blockId) {
    showSaving();
    fetch(`/learning/api/block/duplicate/${blockId}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
        showSaved();
        if (data.success) {
            currentBlocks.push(data.block);
            renderBlocks();
        }
    });
}

function deleteBlock(blockId) {
    if (!confirm('¿Deseas eliminar este bloque?')) return;

    showSaving();
    fetch(`/learning/api/block/delete/${blockId}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
        showSaved();
        if (data.success) {
            currentBlocks = currentBlocks.filter(b => b.id !== blockId);
            renderBlocks();
        }
    });
}

// Configuración de Modal
function openBlockConfigModal(blockId) {
    editingBlockId = blockId;
    const blk = currentBlocks.find(b => b.id === blockId);
    if (!blk) return;

    const modalBody = document.getElementById('blockConfigModalBody');
    const modalTitle = document.getElementById('blockConfigModalTitle');
    modalTitle.innerHTML = `<i class="${getBlockIcon(blk.tipo)} me-2"></i>Configurar ${getBlockTypeName(blk.tipo)}`;

    const cfg = blk.configuracion || {};

    let html = '';
    if (blk.tipo === 'title') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Texto del Título</label>
                <input type="text" id="cfg_title" class="form-control" value="${cfg.title || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Subtítulo</label>
                <input type="text" id="cfg_subtitle" class="form-control" value="${cfg.subtitle || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Nivel de Encabezado</label>
                <select id="cfg_level" class="form-select">
                    <option value="h1" ${cfg.level === 'h1' ? 'selected' : ''}>H1 - Título Principal</option>
                    <option value="h2" ${cfg.level === 'h2' ? 'selected' : ''}>H2 - Sección</option>
                    <option value="h3" ${cfg.level === 'h3' ? 'selected' : ''}>H3 - Subsección</option>
                </select>
            </div>
        `;
    } else if (blk.tipo === 'text') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Contenido Enriquecido (HTML o Texto)</label>
                <textarea id="cfg_content" class="form-control" rows="8">${cfg.content || ''}</textarea>
            </div>
        `;
    } else if (blk.tipo === 'image') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Subir Imagen o URL</label>
                <input type="file" id="cfg_file" class="form-control mb-2" accept="image/*" onchange="uploadMediaFile(this, 'cfg_src')">
                <input type="text" id="cfg_src" class="form-control" placeholder="Ruta de la imagen" value="${cfg.src || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Texto Alternativo (Alt Text)</label>
                <input type="text" id="cfg_alt" class="form-control" value="${cfg.alt || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Pie de Imagen</label>
                <input type="text" id="cfg_caption" class="form-control" value="${cfg.caption || ''}">
            </div>
        `;
    } else if (blk.tipo === 'video') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Subir Video MP4/WEBM o Pegar URL (YouTube/Vimeo)</label>
                <input type="file" id="cfg_file" class="form-control mb-2" accept="video/mp4,video/webm" onchange="uploadMediaFile(this, 'cfg_url')">
                <input type="text" id="cfg_url" class="form-control" placeholder="URL o ruta del video" value="${cfg.url || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Descripción / Leyenda</label>
                <input type="text" id="cfg_caption" class="form-control" value="${cfg.caption || ''}">
            </div>
        `;
    } else if (blk.tipo === 'question') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Tipo de Pregunta</label>
                <select id="cfg_qtype" class="form-select">
                    <option value="single_choice" ${cfg.question_type === 'single_choice' ? 'selected' : ''}>Respuesta Única</option>
                    <option value="multiple_choice" ${cfg.question_type === 'multiple_choice' ? 'selected' : ''}>Opción Múltiple</option>
                    <option value="true_false" ${cfg.question_type === 'true_false' ? 'selected' : ''}>Verdadero / Falso</option>
                    <option value="short_answer" ${cfg.question_type === 'short_answer' ? 'selected' : ''}>Respuesta Corta</option>
                    <option value="fill_blank" ${cfg.question_type === 'fill_blank' ? 'selected' : ''}>Completar Espacios</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Enunciado de la Pregunta</label>
                <textarea id="cfg_question" class="form-control" rows="2">${cfg.question || ''}</textarea>
            </div>
            <div class="row mb-3">
                <div class="col">
                    <label class="form-label fw-bold">Puntaje</label>
                    <input type="number" id="cfg_points" class="form-control" value="${cfg.points || 10}" step="0.5">
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Retroalimentación / Explicación</label>
                <input type="text" id="cfg_explanation" class="form-control" value="${cfg.explanation || ''}">
            </div>
        `;
    } else if (blk.tipo === 'quote') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Texto de la Cita / Nota</label>
                <textarea id="cfg_text" class="form-control" rows="3">${cfg.text || ''}</textarea>
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Autor / Fuente</label>
                <input type="text" id="cfg_author" class="form-control" value="${cfg.author || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Estilo</label>
                <select id="cfg_style" class="form-select">
                    <option value="info" ${cfg.style === 'info' ? 'selected' : ''}>Información (Azul)</option>
                    <option value="warning" ${cfg.style === 'warning' ? 'selected' : ''}>Advertencia (Amarillo)</option>
                    <option value="note" ${cfg.style === 'note' ? 'selected' : ''}>Nota Especial</option>
                </select>
            </div>
        `;
    } else if (blk.tipo === 'pdf') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Subir Documento PDF</label>
                <input type="file" class="form-control mb-2" accept=".pdf" onchange="uploadMediaFile(this, 'cfg_src')">
                <input type="text" id="cfg_src" class="form-control" placeholder="Ruta del archivo PDF" value="${cfg.src || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Título del Documento</label>
                <input type="text" id="cfg_title" class="form-control" value="${cfg.title || 'Documento PDF'}">
            </div>
        `;
    } else if (blk.tipo === 'download') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Subir Archivo Adjunto</label>
                <input type="file" class="form-control mb-2" onchange="uploadMediaFile(this, 'cfg_src')">
                <input type="text" id="cfg_src" class="form-control" placeholder="Ruta del archivo" value="${cfg.src || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Título del Archivo</label>
                <input type="text" id="cfg_title" class="form-control" value="${cfg.title || 'Archivo Descargable'}">
            </div>
        `;
    } else if (blk.tipo === 'audio') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">Subir Archivo de Audio MP3</label>
                <input type="file" class="form-control mb-2" accept="audio/mp3,audio/*" onchange="uploadMediaFile(this, 'cfg_src')">
                <input type="text" id="cfg_src" class="form-control" placeholder="Ruta del audio" value="${cfg.src || ''}">
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold">Título del Audio</label>
                <input type="text" id="cfg_title" class="form-control" value="${cfg.title || 'Narración'}">
            </div>
        `;
    } else if (blk.tipo === 'embed') {
        html = `
            <div class="mb-3">
                <label class="form-label fw-bold">URL de Embed o Código iFrame</label>
                <textarea id="cfg_iframe" class="form-control" rows="4" placeholder="<iframe src=...>${cfg.iframe_code || cfg.url || ''}</textarea>
            </div>
        `;
    } else {
        html = `<p class="text-muted">Este tipo de bloque no requiere configuración adicional.</p>`;
    }

    modalBody.innerHTML = html;
    const modal = new bootstrap.Modal(document.getElementById('blockConfigModal'));
    modal.show();
}

function uploadMediaFile(inputEl, targetInputId) {
    if (!inputEl.files || !inputEl.files[0]) return;
    const file = inputEl.files[0];
    const formData = new FormData();
    formData.append('file', file);

    fetch('/learning/api/upload', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const targetInput = document.getElementById(targetInputId);
            if (targetInput) targetInput.value = data.url;
        } else {
            alert('Error al subir archivo: ' + (data.error || 'tipo no válido'));
        }
    });
}

function saveBlockConfigFromModal() {
    if (!editingBlockId) return;
    const blk = currentBlocks.find(b => b.id === editingBlockId);
    if (!blk) return;

    let cfg = blk.configuracion || {};

    if (blk.tipo === 'title') {
        cfg.title = document.getElementById('cfg_title')?.value || cfg.title;
        cfg.subtitle = document.getElementById('cfg_subtitle')?.value || cfg.subtitle;
        cfg.level = document.getElementById('cfg_level')?.value || cfg.level;
    } else if (blk.tipo === 'text') {
        cfg.content = document.getElementById('cfg_content')?.value || cfg.content;
    } else if (blk.tipo === 'image') {
        cfg.src = document.getElementById('cfg_src')?.value || cfg.src;
        cfg.alt = document.getElementById('cfg_alt')?.value || cfg.alt;
        cfg.caption = document.getElementById('cfg_caption')?.value || cfg.caption;
    } else if (blk.tipo === 'video') {
        cfg.url = document.getElementById('cfg_url')?.value || cfg.url;
        cfg.caption = document.getElementById('cfg_caption')?.value || cfg.caption;
    } else if (blk.tipo === 'question') {
        cfg.question_type = document.getElementById('cfg_qtype')?.value || cfg.question_type;
        cfg.question = document.getElementById('cfg_question')?.value || cfg.question;
        cfg.points = parseFloat(document.getElementById('cfg_points')?.value || cfg.points);
        cfg.explanation = document.getElementById('cfg_explanation')?.value || cfg.explanation;
    } else if (blk.tipo === 'quote') {
        cfg.text = document.getElementById('cfg_text')?.value || cfg.text;
        cfg.author = document.getElementById('cfg_author')?.value || cfg.author;
        cfg.style = document.getElementById('cfg_style')?.value || cfg.style;
    } else if (blk.tipo === 'pdf' || blk.tipo === 'download' || blk.tipo === 'audio') {
        cfg.src = document.getElementById('cfg_src')?.value || cfg.src;
        cfg.title = document.getElementById('cfg_title')?.value || cfg.title;
    } else if (blk.tipo === 'embed') {
        const val = document.getElementById('cfg_iframe')?.value || '';
        if (val.startsWith('<iframe')) {
            cfg.iframe_code = val;
        } else {
            cfg.url = val;
        }
    }

    blk.configuracion = cfg;
    renderBlocks();

    // Guardar en backend
    showSaving();
    const formData = new FormData();
    formData.append('configuracion', JSON.stringify(cfg));

    fetch(`/learning/api/block/update/${editingBlockId}`, { method: 'POST', body: formData })
    .then(r => r.json())
    .then(() => {
        showSaved();
        const modalEl = document.getElementById('blockConfigModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if(modal) modal.hide();
    });
}

// Estructura de Módulos y Lecciones
function createModule(learningId) {
    const titulo = prompt('Nombre del nuevo módulo:');
    if (!titulo) return;

    showSaving();
    const formData = new FormData();
    formData.append('learning_id', learningId);
    formData.append('titulo', titulo);

    fetch('/learning/api/module/create', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        showSaved();
        if (data.success) {
            location.reload();
        }
    });
}

function createLesson(moduleId) {
    const titulo = prompt('Nombre de la nueva lección:');
    if (!titulo) return;

    showSaving();
    const formData = new FormData();
    formData.append('module_id', moduleId);
    formData.append('titulo', titulo);

    fetch('/learning/api/lesson/create', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
        showSaved();
        if (data.success) {
            location.reload();
        }
    });
}

function deleteModule(moduleId) {
    if (!confirm('¿Seguro que deseas eliminar este módulo y todas sus lecciones?')) return;
    fetch(`/learning/api/module/delete/${moduleId}`, { method: 'POST' })
    .then(r => r.json())
    .then(data => {
        if(data.success) location.reload();
    });
}

function showSaving() {
    const el = document.getElementById('saveStatus');
    if (el) el.innerHTML = `<i class="bi bi-arrow-repeat spin me-1 text-primary"></i>Guardando...`;
}

function showSaved() {
    const el = document.getElementById('saveStatus');
    if (el) el.innerHTML = `<i class="bi bi-check-circle-fill text-success me-1"></i>Guardado`;
}
