# DropZone

Une application web simple et efficace pour gérer des fichiers sur votre système local via une interface moderne.

## ✨ Fonctionnalités

-   **Gestion de fichiers :** Affichez les fichiers avec leur nom, taille, checksum (SHA256) et date d'ajout.
-   **Actions rapides :** Renommez, supprimez, copiez l'URL de téléchargement direct pour chaque fichier.
-   **Upload facile :** Zone de glisser-déposer (drag-and-drop) pour l'upload de plusieurs fichiers et bouton de sélection classique.
-   **Opérations asynchrones :** Les calculs de checksum se font en tâche de fond pour ne jamais bloquer l'interface.
-   **Panneau d'administration :** Une zone sécurisée par mot de passe pour les actions de maintenance.
-   **Maintenance simplifiée :** Purgez tous les fichiers ou seulement les logs d'un simple clic.
-   **Thème adaptatif :** L'interface bascule automatiquement entre le mode clair et sombre selon les préférences de votre système.
-   **Conteneurisé :** L'ensemble de l'application et ses services sont gérés par Docker pour une installation et un déploiement faciles.

## 🛠️ Stack Technique

-   **Backend :** Python, Flask, Celery
-   **Frontend :** Bootstrap 5, Dropzone.js, JavaScript
-   **Base de données :** SQLAlchemy (avec SQLite par défaut)
-   **Infrastructure :** Docker, Docker Compose, Redis (pour Celery), Gunicorn

## 🚀 Installation et Lancement

### Prérequis

-   [Docker](https://www.docker.com/get-started)
-   [Docker Compose](https://docs.docker.com/compose/install/)

### Étapes d'installation

1.  **Clonez le projet :**
    ```bash
    git clone [URL_DU_PROJET]
    cd [NOM_DU_DOSSIER]
    ```

2.  **Configurez l'environnement :**
    Créez un fichier nommé `.env` à la racine du projet et ajoutez la configuration suivante. C'est ici que vous définirez votre mot de passe administrateur.

    ```
    # Fichier: .env
    
    # Clé secrète pour Flask (peut être n'importe quelle chaîne de caractères)
    SECRET_KEY=une-super-cle-secrete-a-changer
    
    # Mot de passe pour le panneau d'administration
    ADMIN_PASSWORD=votre_mot_de_passe_admin_ici
    ```

3.  **Lancez l'application avec Docker Compose :**
    Cette commande va construire les images des conteneurs et démarrer tous les services.

    ```bash
    docker-compose up --build
    ```

4.  **Accédez à l'application :**
    -   L'interface principale est disponible à l'adresse : `http://localhost:5000`
    -   Le panneau d'administration est disponible à l'adresse : `http://localhost:5000/admin`

