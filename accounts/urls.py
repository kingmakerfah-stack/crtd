from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .token_serializer import CustomTokenObtainPairView

urlpatterns = [

    # Login endpoint (email + password)
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),

    # Refresh token endpoint
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]