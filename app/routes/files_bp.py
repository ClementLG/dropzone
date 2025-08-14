import os
import json
import shutil
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from werkzeug.utils import secure_filename
from sqlalchemy import text, asc
from ..models import db, Item, Log
from ..utils import sizeof_fmt
from ..tasks import process_file_checksum, assemble_chunks

files_bp = Blueprint('files_bp', __name__)


# --- Fonctions Utilitaires Internes ---

def get_or_create_directory_path(full_path, parent_id):
    """Crée récursivement les dossiers en BDD et sur le disque si nécessaire."""
    current_parent_id = parent_id
    base_path = ''
    if parent_id:
        parent_folder = Item.query.get(parent_id)
        if parent_folder:
            base_path = parent_folder.path

    path_parts = full_path.strip(os.path.sep).split(os.path.sep)

    for part in path_parts:
        if not part: continue
        current_path = os.path.join(base_path, part)
        directory = Item.query.filter_by(path=current_path).first()
        if not directory:
            safe_name = secure_filename(part)

            physical_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_path)
            os.makedirs(physical_path, exist_ok=True)

            directory = Item(name=safe_name, item_type='directory', path=current_path, parent_id=current_parent_id)
            db.session.add(directory)
            db.session.commit()
        current_parent_id = directory.id

    return current_parent_id


# Helper function to be used in this blueprint
def load_persistent_config():
    """Charge la configuration depuis config.json."""
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config.json')
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    return {}


# --- Routes API ---

@files_bp.route('/public-config', methods=['GET'])
def get_public_config():
    """Retourne la configuration non-sensible pour le client."""
    persistent_config = load_persistent_config()
    max_upload_mb = persistent_config.get('MAX_UPLOAD_MB', current_app.config['MAX_UPLOAD_MB'])
    chunk_size_mb = persistent_config.get('CHUNK_SIZE_MB', current_app.config['CHUNK_SIZE_MB'])
    default_expiration = persistent_config.get('DEFAULT_EXPIRATION_MINUTES',
                                               current_app.config['DEFAULT_EXPIRATION_MINUTES'])
    max_expiration = persistent_config.get('MAX_EXPIRATION_MINUTES', current_app.config['MAX_EXPIRATION_MINUTES'])

    return jsonify({
        "max_filesize_mb": max_upload_mb,
        "chunk_size_mb": chunk_size_mb,
        "default_expiration_minutes": default_expiration,
        "max_expiration_minutes": max_expiration
    })


@files_bp.route('/items', methods=['GET'])
def list_items():
    """Liste les items (fichiers/dossiers) et le chemin (breadcrumbs)."""
    parent_id_str = request.args.get('parent_id')
    breadcrumbs = []

    if parent_id_str is None or parent_id_str == 'root':
        parent_id = None
        items = Item.query.filter_by(parent_id=None).order_by(Item.item_type.asc(), Item.name.asc()).all()
    else:
        try:
            parent_id = int(parent_id_str)
            parent = Item.query.get_or_404(parent_id)
            items = parent.children.order_by(Item.item_type.asc(), Item.name.asc()).all()

            curr = parent
            while curr:
                breadcrumbs.insert(0, {"id": curr.id, "name": curr.name})
                curr = curr.parent
        except (ValueError, TypeError):
            return jsonify({"error": "parent_id invalide"}), 400

    item_list = [item.to_dict() for item in items]
    for item_data in item_list:
        if item_data['item_type'] == 'file' and item_data['size_bytes'] is not None:
            item_data['size_human'] = sizeof_fmt(item_data['size_bytes'])

    return jsonify({
        "items": item_list,
        "breadcrumbs": breadcrumbs,
        "current_folder_id": parent_id
    })


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """Gère l'upload de fichiers et délègue l'assemblage à une tâche de fond."""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    parent_id_str = request.form.get('parent_id')
    parent_id = int(parent_id_str) if parent_id_str and parent_id_str != 'null' else None

    expiration_minutes_str = request.form.get('expiration_minutes')
    try:
        expiration_minutes = int(expiration_minutes_str)
    except (ValueError, TypeError):
        expiration_minutes = current_app.config['DEFAULT_EXPIRATION_MINUTES']

    persistent_config = load_persistent_config()
    max_minutes = persistent_config.get('MAX_EXPIRATION_MINUTES', current_app.config['MAX_EXPIRATION_MINUTES'])
    if expiration_minutes > max_minutes:
        expiration_minutes = max_minutes

    relative_path = request.form.get('webkitRelativePath')
    target_path = ''
    final_parent_id = parent_id

    if parent_id:
        parent_folder = Item.query.get(parent_id)
        if parent_folder:
            target_path = parent_folder.path

    if relative_path:
        dir_path = os.path.dirname(relative_path)
        if dir_path:
            final_parent_id = get_or_create_directory_path(dir_path, parent_id)
            parent_folder = Item.query.get(final_parent_id)
            if parent_folder:
                target_path = parent_folder.path

    upload_uuid = request.form.get('dzuuid')
    chunk_index = request.form.get('dzchunkindex', type=int)
    total_chunks = request.form.get('dztotalchunkcount', type=int)

    temp_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp', upload_uuid)
    os.makedirs(temp_dir, exist_ok=True)
    file.save(os.path.join(temp_dir, f"{chunk_index}.chunk"))

    if chunk_index < total_chunks - 1:
        return jsonify({"message": "Morceau reçu."}), 200

    assemble_chunks.delay(
        upload_uuid=upload_uuid,
        total_chunks=total_chunks,
        original_filename=file.filename,
        target_path=target_path,
        parent_id=final_parent_id,
        expiration_minutes=expiration_minutes
    )

    return jsonify({"message": "Upload terminé, assemblage en cours..."}), 202


@files_bp.route('/directories', methods=['POST'])
def create_directory():
    """Crée un nouveau dossier."""
    data = request.get_json()
    name = data.get('name')
    parent_id_str = data.get('parent_id')
    parent_id = int(parent_id_str) if parent_id_str else None

    if not name:
        return jsonify({"error": "Le nom du dossier est requis."}), 400

    safe_name = secure_filename(name)
    parent_path = ''
    if parent_id:
        parent_folder = Item.query.get_or_404(parent_id)
        parent_path = parent_folder.path

    new_path = os.path.join(parent_path, safe_name)

    if Item.query.filter_by(path=new_path).first():
        return jsonify({"error": "Un dossier ou fichier avec ce nom existe déjà."}), 409

    full_physical_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_path)
    os.makedirs(full_physical_path, exist_ok=True)

    new_dir = Item(name=safe_name, item_type='directory', path=new_path, parent_id=parent_id)
    db.session.add(new_dir)
    log = Log(action="CREATE_DIR", details=f"Dossier '{new_path}' créé.")
    db.session.add(log)
    db.session.commit()

    return jsonify(new_dir.to_dict()), 201


@files_bp.route('/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Supprime un fichier ou un dossier (récursivement)."""
    item = Item.query.get_or_404(item_id)
    physical_path = os.path.join(current_app.config['UPLOAD_FOLDER'], item.path)

    try:
        if item.item_type == 'directory' and os.path.exists(physical_path):
            shutil.rmtree(physical_path)
        elif item.item_type == 'file' and os.path.exists(physical_path):
            os.remove(physical_path)

        log = Log(action="DELETE_ITEM", details=f"Item '{item.path}' supprimé.")
        db.session.add(log)
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "Élément supprimé avec succès."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@files_bp.route('/items/<int:item_id>/rename', methods=['PUT'])
def rename_item(item_id):
    """Renomme un fichier ou un dossier (et met à jour les chemins des enfants)."""
    item = Item.query.get_or_404(item_id)
    new_name_base = request.json.get('name')
    if not new_name_base:
        return jsonify({"error": "Le nom ne peut pas être vide."}), 400

    parent_path = os.path.dirname(item.path)
    old_path = item.path

    if item.item_type == 'file':
        _, ext = os.path.splitext(item.name)
        new_name = f"{secure_filename(new_name_base)}{ext}"
    else:  # directory
        new_name = secure_filename(new_name_base)

    new_path = os.path.join(parent_path, new_name)

    if Item.query.filter_by(path=new_path).first():
        return jsonify({"error": "Ce nom est déjà pris à cet emplacement."}), 409

    old_physical_path = os.path.join(current_app.config['UPLOAD_FOLDER'], old_path)
    new_physical_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_path)

    try:
        os.rename(old_physical_path, new_physical_path)

        if item.item_type == 'directory':
            descendants = Item.query.filter(Item.path.startswith(f"{old_path}/")).all()
            for descendant in descendants:
                descendant.path = descendant.path.replace(old_path, new_path, 1)

        item.name = new_name
        item.path = new_path
        log = Log(action="RENAME_ITEM", details=f"'{old_path}' renommé en '{new_path}'.")
        db.session.add(log)
        db.session.commit()
        return jsonify({"message": "Élément renommé avec succès."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@files_bp.route('/download/<int:item_id>/<filename>', methods=['GET'])
def download_file(item_id, filename):
    """Sert un fichier au téléchargement."""
    item = Item.query.get_or_404(item_id)
    if item.name != filename:
        # Optionnel: rediriger vers la bonne URL ou renvoyer une erreur
        return jsonify({"error": "Nom de fichier incorrect."}), 404
    if item.item_type != 'file':
        return jsonify({"error": "Ne peut télécharger que des fichiers."}), 400

    log = Log(action="DOWNLOAD", details=f"Fichier '{item.path}' téléchargé.")
    db.session.add(log)
    db.session.commit()
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], item.path, as_attachment=True)