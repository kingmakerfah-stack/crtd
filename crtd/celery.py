"""
Celery configuration for CRTD project.

This module initializes Celery for asynchronous task processing.
It handles background email sending, scheduled tasks, and other
long-running operations that should not block API responses.

Configuration:
- Broker: Redis (default: localhost:6379)
- Backend: Redis (for storing task results)
- Task serialization: JSON
- Result serialization: JSON
- Timezone: UTC

Usage:
    python manage.py celery worker -l info
    python manage.py celery beat -l info
"""

import os
import sys
import platform
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crtd.settings')

# Initialize Celery app
app = Celery('crtd')

# Load configuration from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY_')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# -------------------------------------------------------
# CELERY CONFIGURATION
# -------------------------------------------------------

# Windows compatibility: Use threads pool on Windows
worker_pool = 'threads' if platform.system() == 'Windows' else 'prefork'

app.conf.update(
    # Broker (Message Queue) - Redis
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    
    # Result Backend - Redis
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    
    # Worker pool for Windows compatibility
    worker_pool=worker_pool,
    
    # Broker connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task Configuration
    task_track_started=True,  # Track when task starts
    task_time_limit=30 * 60,  # Hard time limit: 30 minutes
    task_soft_time_limit=25 * 60,  # Soft time limit: 25 minutes
    
    # Results
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker Configuration
    worker_prefetch_multiplier=4,  # Prefetch 4 tasks at a time
    worker_max_tasks_per_child=1000,  # Recycle worker after 1000 tasks
    
    # Retry Configuration
    task_autoretry_for=(Exception,),
    task_max_retries=3,
)

# -------------------------------------------------------
# CELERY BEAT SCHEDULE (Periodic Tasks)
# -------------------------------------------------------

app.conf.beat_schedule = {
    # Clean expired OTPs every hour
    'clean-expired-otps': {
        'task': 'accounts.tasks.cleanup_expired_otps',
        'schedule': crontab(minute=0),  # Run every hour
        'options': {'queue': 'default'},
    },
    # Send pending emails every 5 minutes
    'send-pending-emails': {
        'task': 'utils.tasks.process_pending_emails',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
        'options': {'queue': 'default'},
    },
}


@app.task(bind=True)
def debug_task(self):
    """
    Debug task for testing Celery setup.
    
    Usage:
        from crtd.celery import debug_task
        debug_task.delay()
    """
    print(f'Request: {self.request!r}')
