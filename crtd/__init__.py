# This will ensure Celery is initialized when Django starts
from .celery import app as celery_app

__all__ = ('celery_app',)
