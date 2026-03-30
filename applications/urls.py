from django.urls import path
from .views import ApplyJobView,CoolDownUpdateView

urlpatterns = [
    path('apply-job/<int:id>/',ApplyJobView.as_view(),name="apply-job"),
    path('admin/cooldown-days/update/',CoolDownUpdateView.as_view(),name="cooldown-days-update")
]
