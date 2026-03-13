# This ensures Celery is initialized when available.
# Allow Django startup in environments where Celery isn't installed.
try:
    from .celery import app as celery_app
except ModuleNotFoundError:
    celery_app = None

__all__ = ("celery_app",)
