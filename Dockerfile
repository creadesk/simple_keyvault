FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    cryptography \
    httpx

COPY vault.py .
COPY vault_client.py .
COPY test_client.py .
COPY entrypoint.sh .

RUN chmod 755 entrypoint.sh

VOLUME ["/data", "/run/keyvault"]

ENTRYPOINT ["/app/entrypoint.sh"]