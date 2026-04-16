from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        # Importing the module connects the audit-log signal handlers.
        from . import audit  # noqa: F401, PLC0415
