from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import LivenessView, ReadinessView

urlpatterns = [
    path("health/live", LivenessView.as_view(), name="health-live"),
    path("health/ready", ReadinessView.as_view(), name="health-ready"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.ledger.urls")),
    path("api/v1/", include("apps.budgets.urls")),
    path("api/v1/", include("apps.analytics.urls")),
    path("api/v1/", include("apps.imports.urls")),
]
