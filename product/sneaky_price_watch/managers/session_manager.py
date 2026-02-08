class SessionManager:
    """
    Manages browsing session lifecycle and configuration.
    """
    def __init__(self):
        self.sessions = {}

    def create_session(self, config):
        """Creates a new browsing session with provided configuration."""
        session_id = self._generate_session_id()
        self.sessions[session_id] = {
            'config': config,
            'created_at': self._get_timestamp(),
            'active': True
        }
        return session_id

    def end_session(self, session_id):
        """Ends a browsing session."""
        if session_id in self.sessions:
            self.sessions[session_id]['active'] = False

    def _generate_session_id(self):
        """Generates a unique session identifier."""
        import uuid
        return str(uuid.uuid4())

    def _get_timestamp(self):
        """Returns current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()