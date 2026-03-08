from celery import Celery
from celery.schedules import crontab

app = Celery('admin_panel')

app.conf.beat_schedule = {
    "delete-expired-admin-otps": {
        "task": "admin_panel.tasks.delete_expired_admin_otps",
        "schedule": 60.0,
    },
}