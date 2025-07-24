from app import create_app, celery as app_celery
from flask import render_template

app = create_app()
celery = app_celery

# Route pour servir la page principale
@app.route('/')
def index():
    return render_template('index.html')

# Route pour la page admin
@app.route('/admin')
def admin_page():
    return render_template('admin.html') # Assurez-vous que ce fichier existe

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')