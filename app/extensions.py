# app/extensions.py
import threading

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO(cors_allowed_origins="*" )
csrf = CSRFProtect()

# SQLite solo permite un escritor a la vez. En modo threading, varios
# estudiantes pueden disparar un commit al mismo tiempo y chocar con
# "database is locked". Este lock serializa esas escrituras en el orden
# en que llegan (FIFO), en vez de dejarlas competir entre hilos.
db_write_lock = threading.Lock()
