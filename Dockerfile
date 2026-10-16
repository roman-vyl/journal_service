FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JOURNAL_HOST=0.0.0.0 \
    JOURNAL_PORT=8097

WORKDIR /app

RUN addgroup --system journal-service \
    && adduser --system --ingroup journal-service --home /nonexistent --shell /usr/sbin/nologin journal-service

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install .

USER journal-service

EXPOSE 8097

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 CMD python -c "import os, urllib.request; port = os.environ.get('JOURNAL_PORT', '8097'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).read()"

ENTRYPOINT ["journal-service"]
