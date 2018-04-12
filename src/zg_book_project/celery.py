import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zg_book_project.settings')

from celery import Celery
from django.conf import settings

app = Celery('zg_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
