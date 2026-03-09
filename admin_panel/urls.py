from django.urls import path
from .views import AdminRegisterView

urlpatterns = [
    path("register/", AdminRegisterView.as_view()),
]