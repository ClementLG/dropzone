import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename
from ..models import db, File, Log
from ..utils import sizeof_fmt
from ..tasks import process_file_checksum

files_bp = Blueprint('files_bp', __name__)


@files_bp.route('/files', methods=['GET'])
def list_files():
    """Liste tous les fichiers."""
    files = File.query.order_by(File.created_at.desc()).all()
    file_list = []
    for f in files:
        file_data = f.to_dict()
        file_data['size_human'] = sizeof_fmt(f.size_bytes)
        file_list.append(file_data)
    return jsonify(file_list)


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """Gère l'upload de fichiers."""
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nom de fichier vide"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        if os.path.exists(filepath):
            return jsonify({"error": "Un fichier avec ce nom existe déjà."}), 409

        file.save(filepath)
        file_size = os.path.getsize(filepath)
        new_file = File(filename=filename, size_bytes=file_size)
        db.session.add(new_file)
        log = Log(action="UPLOAD", details=f"Fichier '{filename}' uploadé.")
        db.session.add(log)
        db.session.commit()
        process_file_checksum.delay(new_file.id)
        return jsonify({"message": "Fichier uploadé avec succès. Traitement en cours.", "file_id": new_file.id}), 201


@files_bp.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Supprime un fichier."""
    file_to_delete = File.query.get_or_404(file_id)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file_to_delete.filename)

    try:
        os.remove(filepath)
        log = Log(action="DELETE", details=f"Fichier '{file_to_delete.filename}' supprimé.")
        db.session.add(log)
        db.session.delete(file_to_delete)
        db.session.commit()
        return jsonify({"message": "Fichier supprimé avec succès."})
    except FileNotFoundError:
        return jsonify({"error": "Fichier non trouvé sur le disque."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    """Sert un fichier au téléchargement."""
    file_record = File.query.get_or_404(file_id)
    log = Log(action="DOWNLOAD", details=f"Fichier '{file_record.filename}' téléchargé.")
    db.session.add(log)
    db.session.commit()
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], file_record.filename, as_attachment=True)


@files_bp.route('/files/<int:file_id>/rename', methods=['PUT'])
def rename_file(file_id):
    """Renomme un fichier."""
    file_to_rename = File.query.get_or_404(file_id)
    data = request.get_json()
    new_name_base = data.get('new_name')

    if not new_name_base:
        return jsonify({"error": "Le nouveau nom ne peut pas être vide."}), 400

    old_name_base, extension = os.path.splitext(file_to_rename.filename)
    new_filename = f"{secure_filename(new_name_base)}{extension}"

    if new_filename == file_to_rename.filename:
        return jsonify({"message": "Le nouveau nom est identique à l'ancien."}), 200

    old_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file_to_rename.filename)
    new_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)

    if os.path.exists(new_filepath):
        return jsonify({"error": "Un fichier avec ce nom existe déjà."}), 409

    try:
        os.rename(old_filepath, new_filepath)

        original_name = file_to_rename.filename
        file_to_rename.filename = new_filename

        log = Log(action="RENAME", details=f"Fichier '{original_name}' renommé en '{new_filename}'.")
        db.session.add(log)
        db.session.commit()

        return jsonify({"message": "Fichier renommé avec succès."})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500