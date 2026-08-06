# Spectra - AI-Powered Reverse Engineering Agent
# Dockerfile for CLI usage

FROM python:3.11-slim

# Set metadata
LABEL maintainer="alicangnll"
LABEL description="Spectra - AI-Powered Reverse Engineering Agent"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SPECTRA_HOME=/spectra \
    SPECTRA_DATA=/spectra/data

# Set working directory
WORKDIR /spectra

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    vim \
    grep \
    findutils \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the application
COPY spectra/ ./spectra/
COPY spectra_cli.py .
COPY README.md .
COPY LICENSE .

# Create data directory for persistent storage
RUN mkdir -p /spectra/data/{sessions,skills,logs} && \
    chmod -R 755 /spectra/data

# Create a non-root user for running the application
RUN useradd -m -u 1000 spectra && \
    chown -R spectra:spectra /spectra

# Switch to non-root user
USER spectra

# Set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose no ports (CLI only)
# If adding web UI later, expose appropriate ports

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command shows help
CMD ["--help"]
