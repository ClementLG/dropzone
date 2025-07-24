import os
import hashlib
from . import celery, db, create_app
from .models import File, Log


@celery.task
def process_file_checksum(file_id):
    """Tâche de fond pour calculer le checksum SHA256 d'un fichier."""
    app = create_app()  # Crée un contexte d'application pour la tâche
    with app.app_context():
        file_record = File.query.get(file_id)
        if not file_record:
            return

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_record.filename)

        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                # Lire le fichier par morceaux pour ne pas surcharger la mémoire
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            file_record.sha256 = sha256_hash.hexdigest()
            file_record.status = 'processed'

            # Log l'action
            log_entry = Log(action="CHECKSUM_CALCULATED", details=f"Checksum pour '{file_record.filename}' calculé.")
            db.session.add(log_entry)

        except FileNotFoundError:
            file_record.status = 'error'
            log_entry = Log(action="CHECKSUM_ERROR",
                            details=f"Fichier '{file_record.filename}' non trouvé pour le calcul du checksum.")
            db.session.add(log_entry)

        finally:
            db.session.commit()