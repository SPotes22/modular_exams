class ModeRegistry:
    def __init__(self):
        self._classes = {}

    def register(self, mode_cls):
        self._classes[mode_cls.name] = mode_cls
        return mode_cls

    def get(self, name, socketio, manager):
        mode_cls = self._classes.get(name) or self._classes['instant_feedback']
        return mode_cls(socketio, manager)


registry = ModeRegistry()
