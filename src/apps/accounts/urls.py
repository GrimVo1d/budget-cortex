from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AccountViewSet, LogoutView, RegisterView, TokenRefreshThrottledView, TokenView

router = DefaultRouter()
router.register(r"accounts", AccountViewSet, basename="account")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/token/", TokenView.as_view(), name="auth-token"),
    path("auth/token/refresh/", TokenRefreshThrottledView.as_view(), name="auth-token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    *router.urls,
]
