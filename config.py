import os
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'une-cle-secrete-difficile-a-deviner'

    # La base de données est déplacée dans le dossier partagé 'uploads'
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(UPLOAD_FOLDER, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'

    MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', 8192))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024