from flask import render_template, send_from_directory, current_app
from flask_login import login_required
from app.blueprints.media import media_bp

@media_bp.route('/media/video/<path:filename>')
@login_required
def stream_video(filename):
    return send_from_directory(current_app.config.get('VIDEO_FOLDER', 'videos'), filename)
