# audit_log/middleware.py

import threading

_thread_locals = threading.local()

class RequestUserMiddleware:
    """
    Middleware to store the current request's user in a thread-safe way.
    This allows us to access the 'actor' in the signal handler.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        response = self.get_response(request)
        return response

def get_current_user():
    """
    Helper function to retrieve the user from thread-local storage.
    """
    return getattr(_thread_locals, 'user', None)