import os
from dotenv import load_dotenv

load_dotenv()
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'une-cle-secrete-difficile-a-deviner'

    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    DB_FOLDER = os.path.join(basedir, 'database')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(DB_FOLDER, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuration Celery (noms de variables modernisés)
    broker_url = 'redis://redis:6379/0'
    result_backend = 'redis://redis:6379/0'

    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin'

    # Configuration de l'upload
    MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', 8192))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

    CHUNK_SIZE_MB = int(os.environ.get('CHUNK_SIZE_MB', 5))