import pytest

@pytest.fixture(autouse=True)
def celery_test_mode(settings):
    """Run Celery tasks synchronously during tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.CELERY_BROKER_URL = "memory://"
    settings.CELERY_RESULT_BACKEND = "cache+memory://"
