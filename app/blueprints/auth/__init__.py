from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

from . import routes  # Importamos las rutas al final para evitar importación circular
