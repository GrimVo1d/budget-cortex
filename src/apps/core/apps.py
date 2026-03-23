from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        # Importing the module wires up the post_save/post_delete signal
        # handlers that populate the audit log.
        from . import audit  # noqa: F401
