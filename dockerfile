# Étape 1: Utiliser une image Python officielle
FROM python:3.11-slim

# Étape 2: Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Étape 3: Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Étape 4: Copier le code de l'application
COPY . .

# Étape 5: Exposer le port que Gunicorn utilisera
EXPOSE 5000

# Étape 6: Commande pour lancer l'application (ne pas lancer directement, docker-compose s'en chargera)
# La commande sera définie dans docker-compose.yml