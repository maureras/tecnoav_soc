FROM mcr.microsoft.com/devcontainers/python:3.12

# Opcional: paquetes del sistema (útil si luego instalas libs con dependencias nativas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*