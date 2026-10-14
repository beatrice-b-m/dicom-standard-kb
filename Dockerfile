FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DICOM_KB_CACHE_DIR=/data/dicom-standard-kb

WORKDIR /app
COPY pyproject.toml README.md uv.lock /app/
COPY src /app/src

# Install the locked dependency versions, including the MCP server's, so
# `mcp serve` works and rebuilds don't pick up new releases.
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --extra mcp --no-emit-project \
        -o /tmp/requirements.txt \
    && pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt \
    && pip install --no-cache-dir --no-deps . \
    && pip uninstall -y uv \
    && rm /tmp/requirements.txt

VOLUME ["/data/dicom-standard-kb"]
ENTRYPOINT ["dicom-kb"]
