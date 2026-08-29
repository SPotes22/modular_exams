from flask import Blueprint

polls_bp = Blueprint('polls', __name__)

from app.blueprints.polls import routes  # noqa: F401, E402
