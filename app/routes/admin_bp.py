from flask import Blueprint, jsonify, request, current_app
from ..models import db, File, Log
from ..utils import admin_required
import os

admin_bp = Blueprint('admin_bp', __name__)


@admin_bp.route('/login', methods=['POST'])
def admin_login():
    """Vérifie le mot de passe admin."""
    password = request.json.get('password')
    if password == current_app.config['ADMIN_PASSWORD']:
        return jsonify({"message": "Authentification réussie"}), 200
    return jsonify({"error": "Mot de passe incorrect"}), 401


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


@admin_bp.route('/config', methods=['GET'])
@admin_required
def get_config():
    """Retourne la configuration actuelle, protégé."""
    return jsonify({
        "upload_folder": current_app.config['UPLOAD_FOLDER'],
        "max_storage": "Non implémenté",
        "database_uri": current_app.config['SQLALCHEMY_DATABASE_URI']
    })


@admin_bp.route('/purge', methods=['POST'])
@admin_required
def purge_files():
    """Supprime tous les fichiers du dossier d'upload et vide la table des fichiers."""
    upload_folder = current_app.config['UPLOAD_FOLDER']
    deleted_files_count = 0
    errors = []

    try:
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    deleted_files_count += 1
            except Exception as e:
                errors.append(f"Impossible de supprimer {filename}: {e}")

        num_rows_deleted = db.session.query(File).delete()

        log_entry = Log(action="PURGE",
                        details=f"{deleted_files_count} fichier(s) supprimé(s) du disque et {num_rows_deleted} entrée(s) de la base de données.")
        db.session.add(log_entry)
        db.session.commit()

        if errors:
            return jsonify(
                {"message": "Purge partielle terminée avec des erreurs.", "deleted_count": deleted_files_count,
                 "errors": errors}), 500

        return jsonify({"message": "Purge terminée avec succès.", "deleted_count": deleted_files_count}), 200

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