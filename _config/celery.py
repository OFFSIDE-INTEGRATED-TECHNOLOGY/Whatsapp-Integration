from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "_config.test_settings")

app = Celery("_config")

# Load config from Django settings (use CELERY_ prefix)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
