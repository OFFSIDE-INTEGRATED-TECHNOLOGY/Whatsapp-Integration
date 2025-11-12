FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

CMD ["celery", "-A", "_config", "worker", "-l", "info", "--concurrency=4"]
