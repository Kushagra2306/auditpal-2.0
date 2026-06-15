# AuditPal Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install minimal dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    streamlit>=1.32.0 \
    notebooklm-py>=0.3.0 \
    fpdf2>=2.7.0 \
    python-dotenv>=1.0.0 \
    pydantic>=2.6.0 \
    pydantic-settings>=2.2.0

# Copy project files
COPY app.py .
COPY config.py .
COPY components/ ./components/
COPY services/ ./services/
COPY utils/ ./utils/

# Create directories
RUN mkdir -p /app/data /root/.notebooklm

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
