from contextvars import ContextVar

_user_id_context : ContextVar[int | None] = ContextVar('user_id',default=None)

def get_current_user_id()->int | None:
    """"Get current user id from context"""
    return _user_id_context.get()

def set_current_user_id(user_id : int)->None:
    """Set current user id from context"""
    return _user_id_context.set(user_id)