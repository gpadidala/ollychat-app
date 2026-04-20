FROM python:3.12-slim

# ─── Optional corporate-network build args ────────────────────────────
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ARG PIP_INDEX_URL=
ARG PIP_TRUSTED_HOST=
ARG CA_CERT_PATH=

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

# Inject a corporate CA bundle if the build provided one (optional).
COPY ${CA_CERT_PATH:-requirements.txt} /tmp/maybe-ca.crt
RUN if grep -qE "^-----BEGIN CERTIFICATE-----" /tmp/maybe-ca.crt 2>/dev/null; then \
      apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
      cp /tmp/maybe-ca.crt /usr/local/share/ca-certificates/corp-ca.crt && \
      update-ca-certificates && \
      rm -rf /var/lib/apt/lists/* ; \
    fi && rm -f /tmp/maybe-ca.crt

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/models', timeout=3)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
