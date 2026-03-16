from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TagViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"tags", TagViewSet, basename="tag")

urlpatterns = router.urls
