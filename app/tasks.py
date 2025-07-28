import os
import hashlib
import shutil
import json
from datetime import datetime, timedelta
from . import celery, db, create_app
from .models import Item, Log
from werkzeug.utils import secure_filename


@celery.task
def assemble_chunks(upload_uuid, total_chunks, original_filename, target_path, parent_id, expiration_minutes):
    """Tâche de fond pour assembler les fichiers, calculer le checksum ET définir leur date d'expiration."""
    app = create_app()
    with app.app_context():
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'tmp', upload_uuid)
        final_filename = secure_filename(original_filename)
        final_item_path = os.path.join(target_path, final_filename)
        final_filepath_on_disk = os.path.join(app.config['UPLOAD_FOLDER'], final_item_path)

        if Item.query.filter_by(path=final_item_path).first():
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return

        sha256_hash = hashlib.sha256()
        try:
            destination_dir = os.path.dirname(final_filepath_on_disk)
            os.makedirs(destination_dir, exist_ok=True)

            with open(final_filepath_on_disk, 'wb') as final_file:
                for i in range(total_chunks):
                    chunk_path = os.path.join(temp_dir, f"{i}.chunk")
                    with open(chunk_path, 'rb') as chunk_file:
                        chunk_content = chunk_file.read()
                        sha256_hash.update(chunk_content)
                        final_file.write(chunk_content)

            shutil.rmtree(temp_dir)
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            log_error = Log(action="ASSEMBLY_ERROR", details=f"Erreur pour {final_filename}: {e}")
            db.session.add(log_error)
            db.session.commit()
            return

        final_checksum = sha256_hash.hexdigest()
        file_size = os.path.getsize(final_filepath_on_disk)

        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=expiration_minutes)

        new_item = Item(name=final_filename, item_type='file', path=final_item_path,
                        parent_id=parent_id, size_bytes=file_size,
                        status='processed', sha256=final_checksum,
                        created_at=now, expires_at=expires_at)
        db.session.add(new_item)
        log = Log(action="UPLOAD_SUCCESS", details=f"Fichier '{final_filename}' assemblé et checksum calculé.")
        db.session.add(log)
        db.session.commit()


@celery.task
def delete_expired_files():
    """Supprime tous les fichiers dont la date d'expiration est dépassée."""
    app = create_app()
    with app.app_context():
        now = datetime.utcnow()
        expired_items = Item.query.filter(Item.item_type == 'file', Item.expires_at <= now).all()

        if not expired_items:
            print("Aucun fichier expiré à supprimer.")
            return "Aucun fichier expiré à supprimer."

        deleted_count = 0
        for item in expired_items:
            try:
                physical_path = os.path.join(app.config['UPLOAD_FOLDER'], item.path)
                if os.path.exists(physical_path):
                    os.remove(physical_path)

                db.session.delete(item)
                deleted_count += 1
            except Exception as e:
                log_error = Log(action="DELETE_EXPIRED_ERROR", details=f"Erreur pour {item.path}: {e}")
                db.session.add(log_error)

        if deleted_count > 0:
            log_purge = Log(action="AUTO_PURGE", details=f"{deleted_count} fichier(s) expiré(s) supprimé(s).")
            db.session.add(log_purge)

        db.session.commit()
        return f"{deleted_count} fichier(s) expiré(s) supprimé(s)."


@celery.task
def cleanup_empty_directories():
    """Vérifie la configuration et supprime les dossiers vides si nécessaire."""
    app = create_app()
    with app.app_context():
        CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        persistent_config = {}
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                persistent_config = json.load(f)

        cleanup_hours = persistent_config.get('CLEANUP_EMPTY_FOLDERS_HOURS', app.config['CLEANUP_EMPTY_FOLDERS_HOURS'])

        if cleanup_hours == 0:
            return "Nettoyage des dossiers vides désactivé."

        state_file = os.path.join(app.config['DB_FOLDER'], 'cleanup_state.json')
        now = datetime.utcnow()

        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                last_run_str = state.get('last_run')
                if last_run_str:
                    last_run = datetime.fromisoformat(last_run_str)
                    if (now - last_run) < timedelta(hours=cleanup_hours):
                        return f"Nettoyage non requis. Prochain passage après {last_run + timedelta(hours=cleanup_hours)}."

        upload_folder = app.config['UPLOAD_FOLDER']
        deleted_folders_paths = []

        for dirpath, dirnames, filenames in os.walk(upload_folder, topdown=False):
            if dirpath == upload_folder or os.path.basename(dirpath) == 'tmp':
                continue

            if not dirnames and not filenames:
                try:
                    relative_path = os.path.relpath(dirpath, upload_folder).replace('\\', '/')
                    item_in_db = Item.query.filter_by(path=relative_path, item_type='directory').first()

                    os.rmdir(dirpath)
                    if item_in_db:
                        db.session.delete(item_in_db)

                    deleted_folders_paths.append(relative_path)
                except OSError as e:
                    print(f"Erreur lors de la suppression de {dirpath}: {e}")
                    continue

        if deleted_folders_paths:
            log_cleanup = Log(action="AUTO_CLEANUP_EMPTY",
                              details=f"{len(deleted_folders_paths)} dossier(s) vide(s) supprimé(s).")
            db.session.add(log_cleanup)

        with open(state_file, 'w') as f:
            json.dump({'last_run': now.isoformat()}, f)

        db.session.commit()
        return f"Nettoyage terminé. {len(deleted_folders_paths)} dossier(s) supprimé(s)."


@celery.task
def process_file_checksum(item_id):
    """
    Cette tâche n'est plus utilisée dans le flux d'upload,
    mais peut être conservée pour des recalculs manuels futurs.
    """
    app = create_app()
    with app.app_context():
        item_record = Item.query.get(item_id)
        if not item_record or item_record.item_type != 'file':
            return

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], item_record.path)

        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            item_record.sha256 = sha256_hash.hexdigest()
            item_record.status = 'processed'

            log_entry = Log(action="CHECKSUM_CALCULATED", details=f"Checksum pour '{item_record.path}' recalculé.")
            db.session.add(log_entry)

        except FileNotFoundError:
            item_record.status = 'error'
            log_entry = Log(action="CHECKSUM_ERROR", details=f"Fichier '{item_record.path}' non trouvé.")
            db.session.add(log_entry)

        finally:
            db.session.commit()