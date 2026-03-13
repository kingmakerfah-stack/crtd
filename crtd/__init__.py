<<<<<<< HEAD
# This ensures Celery is initialized when available.
# Allow Django startup in environments where Celery isn't installed.
try:
    from .celery import app as celery_app
except ModuleNotFoundError:
    celery_app = None
=======
from .celery import app as celery_app
>>>>>>> c703a367880c5fde76cca46daa7c66a68d5856be

__all__ = ("celery_app",)
