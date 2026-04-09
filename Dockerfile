FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
