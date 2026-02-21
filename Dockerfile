FROM python:3.10-slim

WORKDIR /code

# Install system dependencies for asyncpg and psycopg
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev antiword && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
