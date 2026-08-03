from flask import Blueprint

learning_bp = Blueprint('learning', __name__, url_prefix='/learning')

from app.blueprints.learning import routes  # noqa: F401
