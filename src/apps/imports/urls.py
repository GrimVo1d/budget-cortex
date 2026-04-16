from rest_framework.routers import DefaultRouter

from .views import CsvImportViewSet

router = DefaultRouter()
router.register(r"imports", CsvImportViewSet, basename="import")

urlpatterns = router.urls
