"""
Genera una base de datos SQLite "de demo" con datos ficticios de un profesor
de Python: un banco de preguntas, 4 exámenes, un curso (capacitación) con las
mismas temáticas, y un par de estudiantes con intentos ya entregados (uno de
ellos con una respuesta abierta pendiente de calificar).

Uso:
    cd modular_exams
    ./venv/Scripts/python.exe scripts/seed_demo_data.py

OJO: Flask-SQLAlchemy resuelve una URI relativa como "sqlite:///database.db"
dentro de la carpeta instance/ (no en la raíz del proyecto), así que este
script genera seed_demo.db ahí mismo: instance/seed_demo.db. Para "pichar"
datos de demo en cualquier momento, con el servidor apagado:

    cd instance
    cp seed_demo.db database.db

Credenciales de prueba:
    Profesor:    python.profe@modularexams.com / python2026
    Estudiantes: ana.torres@demo.com / estudiante123   (y los demás de abajo)
"""
import os
import random
import string
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# URI relativa a propósito: así Flask-SQLAlchemy la resuelve en instance/,
# exactamente donde vive el database.db real que usa run.py.
os.environ['DATABASE_URL'] = 'sqlite:///seed_demo.db'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_DB_PATH = os.path.join(PROJECT_ROOT, 'instance', 'seed_demo.db')

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    User, Bank, Question, QuestionOption, QuestionMatching, QuestionOrder,
    Exam, ExamQuestion, ExamSession, ExamAttempt, StudentAnswer,
    Learning, LearningModule, Lesson, Block,
)
from app.services.exam_content import create_session_question_snapshots  # noqa: E402


def room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def add_mc(bank, statement, category, options, correct_idx, feedback=None, q_type='multiple_choice'):
    q = Question(bank_id=bank.id, question_type=q_type, statement=statement,
                 category=category, feedback_text=feedback)
    db.session.add(q)
    db.session.flush()
    for idx, text in enumerate(options):
        db.session.add(QuestionOption(question_id=q.id, option_text=text, is_correct=(idx == correct_idx)))
    return q


def add_tf(bank, statement, category, correct, feedback=None):
    return add_mc(bank, statement, category, ['Verdadero', 'Falso'], 0 if correct else 1,
                  feedback=feedback, q_type='true_false')


def add_multi(bank, statement, category, options, correct_idxs, feedback=None):
    q = Question(bank_id=bank.id, question_type='multiple_select', statement=statement,
                 category=category, feedback_text=feedback)
    db.session.add(q)
    db.session.flush()
    for idx, text in enumerate(options):
        db.session.add(QuestionOption(question_id=q.id, option_text=text, is_correct=(idx in correct_idxs)))
    return q


def add_matching(bank, statement, category, pairs, feedback=None):
    q = Question(bank_id=bank.id, question_type='matching', statement=statement,
                 category=category, feedback_text=feedback)
    db.session.add(q)
    db.session.flush()
    for left, right in pairs:
        db.session.add(QuestionMatching(question_id=q.id, left_text=left, right_text=right))
    return q


def add_ordering(bank, statement, category, items, feedback=None):
    q = Question(bank_id=bank.id, question_type='ordering', statement=statement,
                 category=category, feedback_text=feedback)
    db.session.add(q)
    db.session.flush()
    for idx, text in enumerate(items, start=1):
        db.session.add(QuestionOrder(question_id=q.id, item_text=text, correct_position=idx))
    return q


def add_open(bank, statement, category, feedback=None):
    q = Question(bank_id=bank.id, question_type='open_answer', statement=statement,
                 category=category, feedback_text=feedback)
    db.session.add(q)
    db.session.flush()
    return q


def attach(exam, question, points, order_index):
    db.session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, points=points, order_index=order_index))


def grade_mc(snap_map, q, selected_idx):
    """Arma un StudentAnswer de opción única/V-F a partir del índice elegido."""
    opts = list(q.options)
    chosen = opts[selected_idx]
    is_correct = bool(chosen.is_correct)
    correct_text = next((o.option_text for o in opts if o.is_correct), None)
    return StudentAnswer(
        question_id=q.id,
        question_snapshot_id=snap_map.get(q.id),
        question_statement=q.statement,
        selected_option_id=chosen.id,
        selected_option_text=chosen.option_text,
        correct_answer_text=correct_text,
        answer_text=chosen.option_text,
        is_correct=is_correct,
        points_awarded=None,  # se completa afuera con el puntaje del examen
    )


def grade_multi(snap_map, q, selected_idxs):
    opts = list(q.options)
    chosen = [opts[i] for i in selected_idxs]
    correct_ids = {o.id for o in opts if o.is_correct}
    chosen_ids = {o.id for o in chosen}
    is_correct = chosen_ids == correct_ids
    correct_text = ', '.join(o.option_text for o in opts if o.is_correct)
    return StudentAnswer(
        question_id=q.id,
        question_snapshot_id=snap_map.get(q.id),
        question_statement=q.statement,
        selected_option_text=', '.join(o.option_text for o in chosen),
        correct_answer_text=correct_text,
        answer_text=', '.join(o.option_text for o in chosen),
        is_correct=is_correct,
        points_awarded=None,
    )


def grade_open(snap_map, q, text, points_awarded=None, is_correct=None):
    return StudentAnswer(
        question_id=q.id,
        question_snapshot_id=snap_map.get(q.id),
        question_statement=q.statement,
        answer_text=text,
        is_correct=is_correct,
        points_awarded=points_awarded if points_awarded is not None else 0.0,
    )


def main():
    if os.path.exists(SEED_DB_PATH):
        os.remove(SEED_DB_PATH)

    app = create_app()
    with app.app_context():
        # ── Profesor de Python ──────────────────────────────────────────
        profe = User(username='Camilo Rojas', first_name='Camilo', last_name='Rojas',
                     email='python.profe@modularexams.com', role='instructor',
                     institution='Academia de Programación', default_exam_view='exams')
        profe.set_password('python2026')
        db.session.add(profe)
        db.session.flush()

        bank = Bank(name='Banco Python', description='Preguntas de Python para los 4 exámenes de demo.',
                    created_by=profe.id)
        db.session.add(bank)
        db.session.flush()

        # ── Banco de preguntas (18, los 7 tipos) ────────────────────────
        q1 = add_mc(bank, '¿Cuál es el tipo de dato de 3.14 en Python?', 'Fundamentos',
                    ['int', 'float', 'str', 'bool'], 1)
        q2 = add_mc(bank, '¿Qué palabra clave se usa para definir una función en Python?', 'Fundamentos',
                    ['func', 'def', 'function', 'lambda'], 1)
        q3 = add_tf(bank, 'En Python, las listas son mutables.', 'Fundamentos', True)
        q4 = add_mc(bank, '¿Cuál es el resultado de 5 // 2 en Python?', 'Fundamentos',
                    ['2.5', '2', '3', '2.0'], 1)
        q5 = add_multi(bank, '¿Cuáles de los siguientes son tipos de datos inmutables en Python?', 'Fundamentos',
                       ['str', 'tuple', 'list', 'int', 'dict'], [0, 1, 3])

        q6 = add_mc(bank, '¿Qué método agrega un elemento al final de una lista?', 'Estructuras de datos',
                    ['append', 'add', 'push', 'insert'], 0)
        q7 = add_mc(bank, "¿Cómo se accede al valor de la clave 'nombre' en un diccionario d?", 'Estructuras de datos',
                    ["d['nombre']", 'd.nombre', 'd->nombre', 'd(nombre)'], 0)
        q8 = add_tf(bank, 'Los conjuntos (sets) en Python permiten elementos duplicados.', 'Estructuras de datos', False)
        q9 = add_matching(bank, 'Empareja cada estructura con su característica principal.', 'Estructuras de datos',
                           [('list', 'Mutable y ordenada'), ('tuple', 'Inmutable y ordenada'),
                            ('dict', 'Pares clave-valor'), ('set', 'Sin elementos duplicados')])
        q10 = add_ordering(bank, 'Ordena los pasos para crear y recorrer una lista.', 'Estructuras de datos',
                            ['Crear la lista', 'Agregar elementos con append()', 'Recorrerla con un for',
                             'Imprimir cada elemento'])

        q11 = add_mc(bank, '¿Qué palabra clave se usa para crear una clase en Python?', 'POO',
                     ['class', 'Class', 'def', 'struct'], 0)
        q12 = add_mc(bank, '¿Cómo se llama el método especial que inicializa un objeto?', 'POO',
                     ['__init__', '__new__', '__start__', '__main__'], 0)
        q13 = add_tf(bank, 'En Python, la herencia permite que una clase use atributos y métodos de otra.', 'POO', True)
        q14 = add_open(bank, 'Explica con tus palabras qué es la encapsulación en programación orientada a objetos.', 'POO')

        q15 = add_mc(bank, '¿Qué bloque se usa para capturar excepciones en Python?', 'Errores y módulos',
                     ['try/except', 'catch/throw', 'on error', 'rescue'], 0)
        q16 = add_mc(bank, '¿Qué palabra clave se usa para importar un módulo?', 'Errores y módulos',
                     ['import', 'include', 'require', 'use'], 0)
        q17 = add_multi(bank, '¿Cuáles son comprensiones válidas en Python?', 'Errores y módulos',
                        ['list comprehension', 'dict comprehension', 'switch comprehension', 'set comprehension'],
                        [0, 1, 3])
        q18 = add_open(bank, 'Describe un caso real en el que usarías manejo de excepciones en un programa.', 'Errores y módulos')

        db.session.commit()

        # ── 4 exámenes ───────────────────────────────────────────────────
        exam1 = Exam(title='Fundamentos de Python', instructions='Preguntas básicas de tipos y control de flujo.',
                     duration_minutes=15, passing_score=60.0, exam_mode='instant_feedback', instructor_id=profe.id)
        exam2 = Exam(title='Estructuras de Datos en Python', instructions='Listas, tuplas, diccionarios y sets.',
                     duration_minutes=20, passing_score=60.0, exam_mode='open_navigation', instructor_id=profe.id)
        exam3 = Exam(title='Programación Orientada a Objetos en Python', instructions='Clases, objetos y herencia.',
                     duration_minutes=20, passing_score=60.0, exam_mode='teacher_paced', instructor_id=profe.id)
        exam4 = Exam(title='Manejo de Errores y Módulos en Python', instructions='Excepciones, import y comprensiones.',
                     duration_minutes=15, passing_score=60.0, exam_mode='instant_feedback', instructor_id=profe.id)
        db.session.add_all([exam1, exam2, exam3, exam4])
        db.session.flush()

        for idx, q in enumerate([q1, q2, q3, q4, q5], start=1):
            attach(exam1, q, 2.0, idx)
        for idx, q in enumerate([q6, q7, q8, q9, q10], start=1):
            attach(exam2, q, 2.0, idx)
        for idx, q in enumerate([q11, q12, q13, q14], start=1):
            attach(exam3, q, 2.5, idx)
        for idx, q in enumerate([q15, q16, q17, q18], start=1):
            attach(exam4, q, 2.5, idx)

        db.session.commit()

        # ── Curso "Python desde Cero" con las mismas temáticas ───────────
        curso = Learning(nombre='Python desde Cero: Fundamentos a POO',
                          descripcion='Capacitación que acompaña a los 4 exámenes de Python.',
                          estado='published', autor_id=profe.id)
        db.session.add(curso)
        db.session.flush()

        modulos = [
            ('Módulo 1: Fundamentos de Python',
             'Variables, tipos de datos y control de flujo.',
             '<p>Python es un lenguaje de tipado dinámico: no declaras el tipo de una variable, '
             'Python lo infiere en tiempo de ejecución. Repasa <code>int</code>, <code>float</code>, '
             '<code>str</code> y <code>bool</code>, y las estructuras <code>if/elif/else</code>.</p>'),
            ('Módulo 2: Estructuras de Datos',
             'Listas, tuplas, diccionarios y conjuntos.',
             '<p>Las <b>listas</b> son mutables y ordenadas; las <b>tuplas</b> son inmutables; los '
             '<b>diccionarios</b> guardan pares clave-valor; los <b>sets</b> no permiten duplicados.</p>'),
            ('Módulo 3: Programación Orientada a Objetos',
             'Clases, objetos, herencia y encapsulación.',
             '<p>Una <code>class</code> define un molde para crear objetos. El método '
             '<code>__init__</code> inicializa cada instancia, y la herencia permite reutilizar '
             'atributos y métodos de otra clase.</p>'),
            ('Módulo 4: Manejo de Errores y Módulos',
             'Excepciones, import y comprensiones de listas.',
             '<p>Usa <code>try/except</code> para manejar errores sin detener el programa, '
             '<code>import</code> para reutilizar código de otros archivos, y comprensiones como '
             '<code>[x for x in rango]</code> para escribir ciclos más cortos.</p>'),
        ]
        quiz_per_module = [
            ('¿Cuál es el resultado de 5 // 2 en Python?', ['2.5', '2', '3', '2.0'], 1),
            ('¿Qué método agrega un elemento al final de una lista?', ['append', 'add', 'push', 'insert'], 0),
            ('¿Cómo se llama el método que inicializa un objeto en Python?', ['__init__', '__new__', '__start__', '__main__'], 0),
            ('¿Qué bloque se usa para capturar excepciones en Python?', ['try/except', 'catch/throw', 'on error', 'rescue'], 0),
        ]

        for m_idx, ((titulo, sub, contenido), (preg, opts, correcta)) in enumerate(zip(modulos, quiz_per_module), start=1):
            mod = LearningModule(learning_id=curso.id, titulo=titulo, descripcion=sub, orden=m_idx)
            db.session.add(mod)
            db.session.flush()

            leccion = Lesson(module_id=mod.id, titulo=f'Lección {m_idx}', descripcion=sub, orden=1)
            db.session.add(leccion)
            db.session.flush()

            db.session.add(Block(lesson_id=leccion.id, tipo='title', orden=1, visible=True,
                                  configuracion={'title': titulo, 'subtitle': sub, 'level': 'h2'}))
            db.session.add(Block(lesson_id=leccion.id, tipo='text', orden=2, visible=True,
                                  configuracion={'content': contenido}))
            db.session.add(Block(lesson_id=leccion.id, tipo='question', orden=3, visible=True,
                                  configuracion={
                                      'question_type': 'single_choice',
                                      'question': preg,
                                      'points': 10.0,
                                      'feedback': '¡Correcto!',
                                      'explanation': 'Repasa el contenido de este módulo si fallaste.',
                                      'options': [
                                          {'id': i + 1, 'text': o, 'is_correct': (i == correcta)}
                                          for i, o in enumerate(opts)
                                      ],
                                  }))

        db.session.commit()

        # ── Estudiantes de prueba (con cuenta real, no invitados) ────────
        estudiantes_info = [
            ('Ana Torres', 'ana.torres@demo.com'),
            ('Luis Gómez', 'luis.gomez@demo.com'),
            ('Marta Ruiz', 'marta.ruiz@demo.com'),
            ('Carlos Peña', 'carlos.pena@demo.com'),
        ]
        estudiantes = []
        for nombre, email in estudiantes_info:
            first, last = nombre.split(' ', 1)
            u = User(username=nombre, first_name=first, last_name=last, email=email, role='student')
            u.set_password('estudiante123')
            db.session.add(u)
            estudiantes.append(u)
        db.session.flush()
        ana, luis, marta, carlos = estudiantes

        # ── Sesión finalizada de "Fundamentos de Python" (3 intentos) ────
        sess1 = ExamSession(exam_id=exam1.id, session_code=room_code(), status='finished',
                             expected_students=3, created_at=datetime.utcnow() - timedelta(days=2))
        db.session.add(sess1)
        db.session.flush()
        snaps1 = create_session_question_snapshots(sess1)
        snap_map1 = {s.original_question_id: s.id for s in snaps1}

        def build_attempt(session, student, answers, attempt_number=1):
            # Primero se completa points_awarded (quedó en None al construir
            # la respuesta) y solo después se puede sumar la nota real.
            for a in answers:
                eq_points = next(eq.points for eq in session.exam.questions if eq.question_id == a.question_id)
                if a.points_awarded is None:
                    a.points_awarded = eq_points if a.is_correct else 0.0

            earned = sum((a.points_awarded or 0.0) for a in answers)
            total = sum(eq.points for eq in session.exam.questions)
            score = round(earned / total * 100.0, 2) if total else 0.0
            attempt = ExamAttempt(student_id=student.id, session_id=session.id, score=score,
                                   status='completed', attempt_number=attempt_number,
                                   earned_points=round(earned, 2), max_points=round(total, 2),
                                   completed_at=session.created_at + timedelta(minutes=random.randint(5, 18)))
            db.session.add(attempt)
            db.session.flush()
            for a in answers:
                a.attempt_id = attempt.id
                db.session.add(a)
            return attempt

        # Ana: todo correcto (100%)
        build_attempt(sess1, ana, [
            grade_mc(snap_map1, q1, 1), grade_mc(snap_map1, q2, 1),
            grade_mc(snap_map1, q3, 0), grade_mc(snap_map1, q4, 1),
            grade_multi(snap_map1, q5, [0, 1, 3]),
        ])
        # Luis: solo 1 de 5 (reprueba)
        build_attempt(sess1, luis, [
            grade_mc(snap_map1, q1, 1), grade_mc(snap_map1, q2, 0),
            grade_mc(snap_map1, q3, 1), grade_mc(snap_map1, q4, 0),
            grade_multi(snap_map1, q5, [2, 4]),
        ])
        # Marta: 3 de 5 (justo aprueba, 60%)
        build_attempt(sess1, marta, [
            grade_mc(snap_map1, q1, 1), grade_mc(snap_map1, q2, 1),
            grade_mc(snap_map1, q3, 0), grade_mc(snap_map1, q4, 0),
            grade_multi(snap_map1, q5, [2, 4]),
        ])
        db.session.commit()

        # ── Sesión finalizada de "Errores y Módulos" con respuesta abierta
        #     pendiente de calificar (Carlos) ──────────────────────────────
        sess4 = ExamSession(exam_id=exam4.id, session_code=room_code(), status='finished',
                             expected_students=1, created_at=datetime.utcnow() - timedelta(hours=5))
        db.session.add(sess4)
        db.session.flush()
        snaps4 = create_session_question_snapshots(sess4)
        snap_map4 = {s.original_question_id: s.id for s in snaps4}

        a15 = grade_mc(snap_map4, q15, 0)
        a16 = grade_mc(snap_map4, q16, 0)
        a17 = grade_multi(snap_map4, q17, [0, 1, 3])
        a18 = grade_open(snap_map4, q18,
                          'Lo usaría al leer un archivo de configuración: si el archivo no existe, '
                          'capturo la excepción y uso valores por defecto en vez de que el programa se caiga.')
        for a in (a15, a16, a17):
            a.points_awarded = 2.5 if a.is_correct else 0.0
        answers_carlos = [a15, a16, a17, a18]

        earned_graded = sum(a.points_awarded for a in (a15, a16, a17))  # q18 queda pendiente
        total_graded = 2.5 * 3  # puntaje máximo de q15+q16+q17 (sin contar q18, aún sin calificar)
        attempt_carlos = ExamAttempt(
            student_id=carlos.id, session_id=sess4.id,
            score=round(earned_graded / total_graded * 100.0, 2),
            status='pending_review', attempt_number=1,
            earned_points=round(earned_graded, 2), max_points=round(total_graded, 2),
            pending_points=2.5,
            completed_at=sess4.created_at + timedelta(minutes=12),
        )
        db.session.add(attempt_carlos)
        db.session.flush()
        for a in answers_carlos:
            a.attempt_id = attempt_carlos.id
            db.session.add(a)
        db.session.commit()

        print(f'Base de demo creada en: {SEED_DB_PATH}')
        print(f'Profesor: {profe.email} / python2026')
        for nombre, email in estudiantes_info:
            print(f'Estudiante: {email} / estudiante123')


if __name__ == '__main__':
    main()
