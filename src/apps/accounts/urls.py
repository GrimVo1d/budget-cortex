from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import AccountViewSet, RegisterView

router = DefaultRouter()
router.register(r"accounts", AccountViewSet, basename="account")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="auth-token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
] + router.urls
