FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DICOM_KB_CACHE_DIR=/data/dicom-standard-kb

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

VOLUME ["/data/dicom-standard-kb"]
ENTRYPOINT ["dicom-kb"]
