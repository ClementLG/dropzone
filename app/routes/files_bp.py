import os
import json
import shutil
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename
from ..models import db, File, Log
from ..utils import sizeof_fmt
from ..tasks import process_file_checksum

files_bp = Blueprint('files_bp', __name__)


@files_bp.route('/public-config', methods=['GET'])
def get_public_config():
    """Retourne la configuration non-sensible pour le client."""
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    max_upload_mb = current_app.config['MAX_UPLOAD_MB']

    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            try:
                persistent_config = json.load(f)
                max_upload_mb = persistent_config.get('MAX_UPLOAD_MB', max_upload_mb)
            except json.JSONDecodeError:
                pass

    return jsonify({
        "max_filesize_mb": max_upload_mb
    })


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
    """Gère l'upload de fichiers, y compris les uploads fractionnés (chunked)."""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    upload_uuid = request.form.get('dzuuid')

    if not upload_uuid:
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
        return jsonify({"message": "Upload simple réussi"}), 201

    chunk_index = request.form.get('dzchunkindex', type=int)
    total_chunks = request.form.get('dztotalchunkcount', type=int)

    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp', upload_uuid)
    os.makedirs(temp_dir, exist_ok=True)

    chunk_path = os.path.join(temp_dir, f"{chunk_index}.chunk")
    file.save(chunk_path)

    if chunk_index < total_chunks - 1:
        return jsonify({"message": f"Morceau {chunk_index + 1}/{total_chunks} reçu."}), 200

    final_filename = secure_filename(file.filename)
    final_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], final_filename)

    if os.path.exists(final_filepath):
        shutil.rmtree(temp_dir)
        return jsonify({"error": "Un fichier avec ce nom existe déjà."}), 409

    try:
        with open(final_filepath, 'wb') as final_file:
            for i in range(total_chunks):
                chunk_to_write_path = os.path.join(temp_dir, f"{i}.chunk")
                with open(chunk_to_write_path, 'rb') as chunk_file:
                    final_file.write(chunk_file.read())

        shutil.rmtree(temp_dir)

    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({"error": f"Erreur lors de l'assemblage du fichier : {e}"}), 500

    file_size = os.path.getsize(final_filepath)
    new_file = File(filename=final_filename, size_bytes=file_size)
    db.session.add(new_file)
    log = Log(action="UPLOAD", details=f"Fichier '{final_filename}' uploadé (en morceaux).")
    db.session.add(log)
    db.session.commit()

    process_file_checksum.delay(new_file.id)

    return jsonify({"message": "Fichier assemblé et uploadé avec succès."}), 201


@files_bp.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Supprime un fichier."""
    file_to_delete = File.query.get_or_404(file_id)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file_to_delete.filename)

    try:
        if os.path.exists(filepath):
            os.remove(filepath)

        log = Log(action="DELETE", details=f"Fichier '{file_to_delete.filename}' supprimé.")
        db.session.add(log)
        db.session.delete(file_to_delete)
        db.session.commit()
        return jsonify({"message": "Fichier supprimé avec succès."})
    except Exception as e:
        db.session.rollback()
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