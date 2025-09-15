# config/settings/development.py
# from .base import *
# DEBUG = True
# ALLOWED_HOSTS = ['localhost','127.0.0.1']


# config/settings/production.py
from .base import *
DEBUG = False
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',')
