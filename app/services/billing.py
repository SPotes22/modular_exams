# app/services/billing.py
"""Planes, prueba gratis y pagos con AVAX (testnet Fuji) verificados on-chain."""
import json
import math
import urllib.request
from datetime import datetime, timedelta
from decimal import Decimal

from flask import current_app

from app.extensions import db
from app.models import Exam, ExamSession, Payment, User

TRIAL_DAYS = 14
PLAN_DAYS = 30
# Una sala sin cerrar deja de contar como "activa" después de este tiempo
ROOM_ACTIVE_WINDOW = timedelta(hours=12)
FINISHED_STATUSES = ['finished', 'FINISHED', 'closed', 'CLOSED']

PLANS = {
    'trial': {'name': 'Prueba gratis', 'instructors': 1, 'max_participants': 10, 'max_rooms': 1},
    'instructor': {'name': 'Instructores', 'instructors': 1, 'max_participants': 20, 'max_rooms': 6,
                   'price_cop': '49.000', 'price_key': 'PRICE_INSTRUCTOR_AVAX'},
    'academia': {'name': 'Academias', 'instructors': 3, 'max_participants': 80, 'max_rooms': 6,
                 'price_cop': '129.000', 'price_key': 'PRICE_ACADEMIA_AVAX'},
}
PAID_PLANS = ('instructor', 'academia')
UNLIMITED_ROLES = ('superuser', 'admin')


class PaymentError(Exception):
    """El pago no se pudo validar; el mensaje se muestra al usuario."""


class PaymentPending(Exception):
    """La transacción aún no está confirmada en la red."""


# ── Estado del plan ─────────────────────────────────────────────────────────

def ensure_trial_started(user):
    if user.trial_started_at is None:
        user.trial_started_at = datetime.utcnow()
        db.session.commit()


def plan_status(user, now=None):
    """Plan efectivo del usuario: {'key', 'name', 'active', 'expires_at', 'days_left', limites...}."""
    now = now or datetime.utcnow()
    if user.role in UNLIMITED_ROLES:
        return {'key': 'admin', 'name': 'Administrador', 'active': True, 'expires_at': None,
                'days_left': None, 'max_participants': None, 'max_rooms': None}

    ensure_trial_started(user)
    if user.plan in PAID_PLANS and user.plan_expires_at and user.plan_expires_at > now:
        key, expires_at = user.plan, user.plan_expires_at
    else:
        key, expires_at = 'trial', user.trial_started_at + timedelta(days=TRIAL_DAYS)

    active = expires_at > now
    plan = PLANS[key]
    return {
        'key': key,
        'name': plan['name'],
        'active': active,
        'expires_at': expires_at,
        'days_left': math.ceil((expires_at - now).total_seconds() / 86400) if active else 0,
        'max_participants': plan['max_participants'],
        'max_rooms': plan['max_rooms'],
    }


def active_room_count(user, now=None):
    now = now or datetime.utcnow()
    return ExamSession.query.join(Exam).filter(
        Exam.instructor_id == user.id,
        ExamSession.status.notin_(FINISHED_STATUSES),
        ExamSession.created_at >= now - ROOM_ACTIVE_WINDOW,
    ).count()


def can_open_room(user):
    """(True, None) si el instructor puede abrir otra sala; si no, (False, mensaje)."""
    status = plan_status(user)
    if status['key'] == 'admin':
        return True, None
    if not status['active']:
        if status['key'] == 'trial':
            return False, 'Tu prueba gratis de 14 días terminó. Elige un plan para seguir abriendo salas.'
        return False, 'Tu plan venció. Renueva tu suscripción para seguir abriendo salas.'
    if active_room_count(user) >= status['max_rooms']:
        return False, (f"Tu plan {status['name']} permite {status['max_rooms']} "
                       f"sala{'s' if status['max_rooms'] != 1 else ''} simultánea"
                       f"{'s' if status['max_rooms'] != 1 else ''}. Cierra una sala o mejora tu plan.")
    return True, None


def room_capacity_error(db_session, connected_count):
    """Mensaje de error si la sala ya alcanzó el máximo de participantes del plan del instructor."""
    exam = db_session.exam if db_session else None
    instructor = db.session.get(User, exam.instructor_id) if exam and exam.instructor_id else None
    if instructor is None:
        return None
    limit = plan_status(instructor)['max_participants']
    if limit is not None and connected_count >= limit:
        return f'Esta sala está llena ({limit} participantes máximo en el plan del instructor).'
    return None


# ── Pagos con AVAX ──────────────────────────────────────────────────────────

def plan_price_avax(plan_key):
    return Decimal(str(current_app.config[PLANS[plan_key]['price_key']]))


def plan_price_wei(plan_key):
    return int(plan_price_avax(plan_key) * Decimal(10) ** 18)


def merchant_address():
    return (current_app.config.get('AVAX_MERCHANT_ADDRESS') or '').strip()


def _rpc(method, params):
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
    req = urllib.request.Request(current_app.config['AVAX_RPC_URL'], data=payload,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            body = json.loads(res.read().decode())
    except Exception as exc:
        raise PaymentError('No se pudo consultar la red de Avalanche. Intenta de nuevo.') from exc
    if body.get('error'):
        raise PaymentError(f"La red respondió con un error: {body['error'].get('message', 'desconocido')}")
    return body.get('result')


def verify_and_activate(user, plan_key, tx_hash):
    """Valida la transacción en Fuji y activa (o extiende) el plan 30 días."""
    if plan_key not in PAID_PLANS:
        raise PaymentError('Plan no válido.')
    tx_hash = (tx_hash or '').strip().lower()
    if not (tx_hash.startswith('0x') and len(tx_hash) == 66):
        raise PaymentError('Hash de transacción no válido.')
    merchant = merchant_address().lower()
    if not merchant:
        raise PaymentError('El pago con AVAX no está configurado (falta AVAX_MERCHANT_ADDRESS).')
    if Payment.query.filter_by(tx_hash=tx_hash).first():
        raise PaymentError('Esta transacción ya fue usada para activar un plan.')

    tx = _rpc('eth_getTransactionByHash', [tx_hash])
    if not tx:
        raise PaymentPending()
    chain_id = int(tx.get('chainId') or '0x0', 16)
    if chain_id != current_app.config['AVAX_CHAIN_ID']:
        raise PaymentError('La transacción no es de la red Avalanche Fuji.')
    if (tx.get('to') or '').lower() != merchant:
        raise PaymentError('La transacción no fue enviada a la billetera de MyTraining.')
    value = int(tx.get('value') or '0x0', 16)
    if value < plan_price_wei(plan_key):
        raise PaymentError(f'El monto enviado es menor al precio del plan ({plan_price_avax(plan_key)} AVAX).')

    receipt = _rpc('eth_getTransactionReceipt', [tx_hash])
    if not receipt:
        raise PaymentPending()
    if receipt.get('status') != '0x1':
        raise PaymentError('La transacción falló en la red.')

    now = datetime.utcnow()
    base = user.plan_expires_at if (user.plan == plan_key and user.plan_expires_at and user.plan_expires_at > now) else now
    user.plan = plan_key
    user.plan_expires_at = base + timedelta(days=PLAN_DAYS)
    user.wallet_address = (tx.get('from') or '').lower() or user.wallet_address
    db.session.add(Payment(user_id=user.id, plan=plan_key, tx_hash=tx_hash, from_address=tx.get('from'),
                           amount_wei=str(value), chain_id=chain_id))
    db.session.commit()
    return user.plan_expires_at
