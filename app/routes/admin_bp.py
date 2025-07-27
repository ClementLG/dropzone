from flask import Blueprint, jsonify, request, current_app
from ..models import db, Item, Log
from ..utils import admin_required
import os
import json
import shutil

admin_bp = Blueprint('admin_bp', __name__)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')


def load_persistent_config():
    """Charge la configuration depuis config.json."""
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


def save_persistent_config(data):
    """Sauvegarde la configuration dans config.json."""
    current_config = load_persistent_config()
    current_config.update(data)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(current_config, f, indent=4)


@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Vérifie le mot de passe admin."""
    password = request.json.get('password')
    if password == current_app.config['ADMIN_PASSWORD']:
        return jsonify({"message": "Authentification réussie"}), 200
    return jsonify({"error": "Mot de passe incorrect"}), 401


@admin_bp.route('/config', methods=['GET', 'POST'])
@admin_required
def handle_config():
    """Gère la configuration (lit et écrit dans config.json)."""
    if request.method == 'POST':
        data = request.get_json()
        current_config = load_persistent_config()

        if 'max_upload_mb' in data:
            try:
                max_size = int(data['max_upload_mb'])
                if max_size < 1:
                    return jsonify({"error": "La taille doit être au moins de 1 Mo."}), 400
                current_config['MAX_UPLOAD_MB'] = max_size
                current_app.config['MAX_CONTENT_LENGTH'] = max_size * 1024 * 1024
            except (ValueError, TypeError):
                return jsonify({"error": "La valeur pour la taille max doit être un nombre entier."}), 400

        if 'chunk_size_mb' in data:
            try:
                chunk_size = int(data['chunk_size_mb'])
                if chunk_size < 1:
                    return jsonify({"error": "La taille des morceaux doit être d'au moins 1 Mo."}), 400
                current_config['CHUNK_SIZE_MB'] = chunk_size
            except (ValueError, TypeError):
                return jsonify({"error": "La valeur pour la taille des morceaux doit être un nombre entier."}), 400

        save_persistent_config(current_config)
        log = Log(action="CONFIG_UPDATE", details=f"Configuration mise à jour : {data}")
        db.session.add(log)
        db.session.commit()
        return jsonify({"message": "Configuration mise à jour."})

    # GET
    persistent_config = load_persistent_config()
    return jsonify({
        "max_upload_mb": persistent_config.get('MAX_UPLOAD_MB', current_app.config['MAX_UPLOAD_MB']),
        "chunk_size_mb": persistent_config.get('CHUNK_SIZE_MB', current_app.config['CHUNK_SIZE_MB']),
    })


@admin_bp.route('/logs', methods=['GET'])
@admin_required
def get_logs():
    """Récupère tous les logs, protégé par le décorateur."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    logs_pagination = Log.query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
    logs = logs_pagination.items
    return jsonify({
        "logs": [log.to_dict() for log in logs],
        "total_pages": logs_pagination.pages,
        "current_page": page
    })


@admin_bp.route('/purge', methods=['POST'])
@admin_required
def purge_files():
    """Supprime tous les items (fichiers/dossiers) et vide le dossier d'upload."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    deleted_items_count = 0
    errors = []

    try:
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            if filename in ['tmp', 'app.db', '.gitkeep']:
                continue
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    deleted_items_count += 1
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    deleted_items_count += 1
            except Exception as e:
                errors.append(f"Impossible de supprimer {filename}: {e}")

        num_rows_deleted = db.session.query(Item).delete()

        log_entry = Log(action="PURGE",
                        details=f"{deleted_items_count} élément(s) supprimé(s) du disque et {num_rows_deleted} entrée(s) de la base de données.")
        db.session.add(log_entry)
        db.session.commit()

        if errors:
            return jsonify(
                {"message": "Purge partielle terminée avec des erreurs.", "deleted_count": deleted_items_count,
                 "errors": errors}), 500

        return jsonify({"message": "Purge terminée avec succès.", "deleted_count": deleted_items_count}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Une erreur grave est survenue lors de la purge: {e}"}), 500


@admin_bp.route('/logs/purge', methods=['POST'])
@admin_required
def purge_logs():
    """Supprime tous les logs de la base de données."""
    try:
        num_rows_deleted = db.session.query(Log).delete()

        log_entry = Log(action="LOG_PURGE", details=f"{num_rows_deleted} entrée(s) de log ont été supprimées.")
        db.session.add(log_entry)

        db.session.commit()
        return jsonify({"message": f"{num_rows_deleted} logs ont été purgés avec succès."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Une erreur est survenue lors de la purge des logs: {e}"}), 500