from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.audit import AuditActorMixin
from apps.core.auth import user_id
from apps.core.exceptions import ApiError
from tasks.imports import parse_csv_import

from .models import CsvImport, ImportStatus
from .serializers import CsvImportSerializer
from .storage import sha256_of, store_upload

logger = logging.getLogger(__name__)

# Room for the multipart envelope and the other form fields around the file.
_MULTIPART_OVERHEAD = 64 * 1024


def _too_large() -> ApiError:
    return ApiError(
        f"file exceeds {settings.IMPORT_MAX_BYTES} bytes",
        code="file_too_large",
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    )


def _enqueue(job: CsvImport) -> bool:
    """Queue the parse task; if the broker is down, fail the job right away."""
    try:
        parse_csv_import.delay(job.pk)
    except Exception:
        logger.exception("csv_import_enqueue_failed", extra={"import_id": job.pk})
        Path(job.file_path).unlink(missing_ok=True)
        job.status = ImportStatus.FAILED
        job.error = "could not queue the import; upload the file again"
        job.save(update_fields=["status", "error", "updated_at"])
        return False
    return True


class CsvImportViewSet(
    AuditActorMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,  # type: ignore[type-arg]
):
    """Upload a bank statement (multipart) and poll the import job."""

    serializer_class = CsvImportSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    filterset_fields = ["status", "fmt"]

    def get_queryset(self) -> QuerySet[CsvImport]:
        if getattr(self, "swagger_fake_view", False):  # schema generation, no user
            return CsvImport.objects.none()
        return CsvImport.objects.filter(user_id=user_id(self.request))

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        # Refuse before the body is read: Django would otherwise spool the
        # whole upload to disk first. (A proxy body limit is still advisable.)
        declared = int(request.META.get("CONTENT_LENGTH") or 0)
        if declared > settings.IMPORT_MAX_BYTES + _MULTIPART_OVERHEAD:
            raise _too_large()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data.pop("file")
        if upload.size > settings.IMPORT_MAX_BYTES:
            raise _too_large()

        file_hash = sha256_of(upload)
        existing = CsvImport.objects.filter(user_id=user_id(request), file_hash=file_hash).first()
        if existing is not None and existing.status != ImportStatus.FAILED:
            raise ApiError(
                f"this file was already imported (import {existing.pk})",
                code="duplicate_file",
                status_code=status.HTTP_409_CONFLICT,
            )

        path = store_upload(upload, user_id(request))
        if existing is not None:
            # A failed attempt with the same file: retry it under the same job.
            Path(existing.file_path).unlink(missing_ok=True)
            job = serializer.update(
                existing,
                {
                    **serializer.validated_data,
                    "file_path": str(path),
                    "status": ImportStatus.PENDING,
                    "error": "",
                },
            )
        else:
            job = serializer.save(user=request.user, file_path=str(path), file_hash=file_hash)
        queued: list[bool] = []
        transaction.on_commit(lambda: queued.append(_enqueue(job)))
        if queued == [False]:
            raise ApiError(
                "the import queue is unavailable, try again later",
                code="queue_unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        job.refresh_from_db()
        return Response(self.get_serializer(job).data, status=status.HTTP_202_ACCEPTED)
