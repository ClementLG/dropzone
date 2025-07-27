import os
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from celery import Celery
from config import Config

# Initialise les extensions au niveau du module
db = SQLAlchemy()
celery = Celery(__name__,
                broker=Config.broker_url,
                backend=Config.result_backend)

# Applique la planification directement à l'instance Celery
celery.conf.beat_schedule = Config.beat_schedule


def create_app():
    """Crée et configure une instance de l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Créer les dossiers nécessaires au démarrage
    upload_folder = app.config['UPLOAD_FOLDER']
    temp_folder = os.path.join(upload_folder, 'tmp')
    db_folder = app.config['DB_FOLDER']

    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(temp_folder, exist_ok=True)
    os.makedirs(db_folder, exist_ok=True)

    # Initialiser les extensions avec l'application
    db.init_app(app)

    # Mettre à jour la configuration de Celery (conserve les autres paramètres de Flask)
    celery.conf.update(app.config)

    # Importer et enregistrer les Blueprints (routes)
    from .routes.files_bp import files_bp
    from .routes.admin_bp import admin_bp
    app.register_blueprint(files_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # Le service 'web' est le seul responsable de la création de la BDD
    if os.environ.get('ROLE') != 'background':
        with app.app_context():
            db.create_all()

    return app