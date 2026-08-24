FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/root/.local/bin:${PATH}"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git build-essential pipx && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pipx install semgrep==1.103.0
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
