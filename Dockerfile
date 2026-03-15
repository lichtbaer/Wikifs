# WikiFS API — Python FastAPI backend
FROM python:3.11-slim

WORKDIR /app

# Install package and dependencies
COPY pyproject.toml .
COPY wikifs/ wikifs/
COPY cli.py server.py config.toml ./
RUN pip install --no-cache-dir -e .

# Persistent data (cache + traces) when WIKIFS_DATA_DIR=/data
ENV WIKIFS_DATA_DIR=/data
EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
