from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.blueprints.billing import billing_bp
from app.models import Payment
from app.services.billing import (PLANS, PAID_PLANS, PaymentError, PaymentPending, active_room_count,
                                  merchant_address, plan_price_avax, plan_price_wei, plan_status,
                                  verify_and_activate)


def _instructor_only():
    if current_user.role != 'instructor':
        flash('Las suscripciones son para cuentas de instructor.', 'warning')
        return redirect(url_for('auth.home'))
    return None


@billing_bp.route('/suscripcion')
@login_required
def subscription():
    denied = _instructor_only()
    if denied:
        return denied

    plans = []
    for key in PAID_PLANS:
        plans.append({
            'key': key,
            'name': PLANS[key]['name'],
            'price_cop': PLANS[key]['price_cop'],
            'price_avax': plan_price_avax(key),
            'price_wei_hex': hex(plan_price_wei(key)),
            'max_participants': PLANS[key]['max_participants'],
            'max_rooms': PLANS[key]['max_rooms'],
        })
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).all()

    return render_template(
        'subscription.html',
        status=plan_status(current_user),
        rooms_in_use=active_room_count(current_user),
        plans=plans,
        selected_plan=request.args.get('plan') if request.args.get('plan') in PAID_PLANS else None,
        payments=payments,
        merchant=merchant_address(),
        chain_id=current_app.config['AVAX_CHAIN_ID'],
        rpc_url=current_app.config['AVAX_RPC_URL'],
    )


@billing_bp.route('/suscripcion/verificar', methods=['POST'])
@login_required
def verify_payment():
    if current_user.role != 'instructor':
        return {'ok': False, 'message': 'Las suscripciones son para cuentas de instructor.'}, 403

    data = request.get_json(silent=True) or {}
    try:
        expires_at = verify_and_activate(current_user, data.get('plan'), data.get('tx_hash'))
    except PaymentPending:
        return {'ok': False, 'pending': True, 'message': 'Esperando confirmación de la red...'}, 202
    except PaymentError as exc:
        return {'ok': False, 'message': str(exc)}, 400

    flash(f"¡Pago confirmado! Tu plan {PLANS[data['plan']]['name']} está activo hasta el "
          f"{expires_at.strftime('%d/%m/%Y')}.", 'success')
    return {'ok': True, 'redirect': url_for('billing.subscription')}
