FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
# Use gunicorn for Django app
CMD ["gunicorn", "_config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
