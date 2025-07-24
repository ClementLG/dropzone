from functools import wraps
from flask import request, jsonify, current_app

def sizeof_fmt(num, suffix="o"):
    """Formate une taille en octets de manière lisible (ko, Mo, Go)."""
    for unit in ["", "k", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Y{suffix}"

def admin_required(f):
    """Décorateur pour sécuriser une route avec un mot de passe admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_password = request.headers.get('X-Admin-Password')
        if not auth_password or auth_password != current_app.config['ADMIN_PASSWORD']:
            return jsonify({"error": "Accès non autorisé"}), 403
        return f(*args, **kwargs)
    return decorated_function