ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    DJANGO_SETTINGS_MODULE=budget_cortex.settings.prod

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Dependencies come from the hash-pinned lock file so image builds are
# reproducible; the layer stays cached until the lock changes.
COPY requirements/runtime.txt /tmp/runtime.txt
# pip itself is not in the lock, so it is removed once the dependencies are in.
RUN python -m pip install --require-hashes -r /tmp/runtime.txt \
 && rm /tmp/runtime.txt \
 && python -m pip uninstall -y pip

COPY --chown=app:app manage.py ./
COPY --chown=app:app src ./src
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
# The media volume inherits this directory's ownership on first mount.
RUN mkdir -p /app/media && chown app:app /app/media

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["api"]


# Tooling image: runtime plus linters and the test stack. Used by the
# `tools` compose service; the repository is bind-mounted over /app.
FROM runtime AS dev

USER root
COPY requirements/dev.txt /tmp/dev.txt
RUN python -m ensurepip \
 && python -m pip install --require-hashes -r /tmp/dev.txt \
 && rm /tmp/dev.txt
USER app
