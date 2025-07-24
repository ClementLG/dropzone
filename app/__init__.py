import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from celery import Celery
from config import Config

# Initialisation des extensions
db = SQLAlchemy()
celery = Celery(__name__, broker=Config.CELERY_BROKER_URL)


def create_app():
    """Crée et configure une instance de l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Créer le dossier d'upload et le sous-dossier tmp s'ils n'existent pas
    upload_folder = app.config['UPLOAD_FOLDER']
    temp_folder = os.path.join(upload_folder, 'tmp')
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(temp_folder, exist_ok=True)

    # Initialiser les extensions avec l'app
    db.init_app(app)

    # Mettre à jour la config de Celery depuis la config Flask
    celery.conf.update(app.config)

    # Importer et enregistrer les Blueprints (routes)
    from .routes.files_bp import files_bp
    from .routes.admin_bp import admin_bp
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Création des tables de la base de données
    with app.app_context():
        db.create_all()

    return app