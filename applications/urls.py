from django.urls import path
from .models import Application
from .views import ApplyJobView
urlpatterns = [
    path('apply-job/<int:id>/',ApplyJobView.as_view())
]
