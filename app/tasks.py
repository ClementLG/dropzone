import os
import hashlib
import shutil
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