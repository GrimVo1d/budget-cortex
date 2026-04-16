"""Where uploaded statements live on disk.

File names are generated server-side; the client's file name is never
used. The worker only opens paths that resolve inside :func:`imports_root`.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


def imports_root() -> Path:
    return (Path(settings.MEDIA_ROOT) / settings.IMPORTS_SUBDIR).resolve()


def sha256_of(upload: UploadedFile[bytes]) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def store_upload(upload: UploadedFile[bytes], user_id: int) -> Path:
    target_dir = imports_root() / str(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}.csv"
    with target.open("wb") as fh:
        for chunk in upload.chunks():
            fh.write(chunk)
    return target


def resolve_stored(path: str) -> Path:
    """Return ``path`` resolved, refusing anything outside the imports root."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(imports_root()):
        raise ValueError(f"import file outside {imports_root()}")
    return resolved
