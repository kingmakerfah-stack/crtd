from django.apps import AppConfig


class PreApplicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pre_application'
