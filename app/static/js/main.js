// Désactive la recherche automatique de Dropzone.
Dropzone.autoDiscover = false;

document.addEventListener('DOMContentLoaded', function() {

    const fileTableBody = document.getElementById('file-table-body');
    const refreshBtn = document.getElementById('refresh-btn');

    // Modales
    const deleteModalEl = document.getElementById('delete-confirm-modal');
    const renameModalEl = document.getElementById('rename-modal');
    const deleteModal = new bootstrap.Modal(deleteModalEl);
    const renameModal = new bootstrap.Modal(renameModalEl);

    // Éléments des modales
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const fileToDeleteName = document.getElementById('file-to-delete-name');
    let fileIdToDelete = null;

    const confirmRenameBtn = document.getElementById('confirm-rename-btn');
    const newFilenameInput = document.getElementById('new-filename-input');
    let fileIdToRename = null;


    // --- Fonctions ---

    const fetchFiles = async () => {
        if(refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '🔄 Chargement...';
        }
        try {
            const response = await fetch('/api/files');
            if (!response.ok) throw new Error('Erreur réseau.');
            const files = await response.json();
            renderFiles(files);
        } catch (error) {
            console.error(error);
            fileTableBody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Impossible de charger les fichiers.</td></tr>`;
        } finally {
            if(refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '🔄 Rafraîchir';
            }
        }
    };

    const renderFiles = (files) => {
        fileTableBody.innerHTML = '';
        if (files.length === 0) {
            fileTableBody.innerHTML = `<tr><td colspan="5" class="text-center">Aucun fichier trouvé.</td></tr>`;
            return;
        }

        files.forEach(file => {
            let checksumHTML = '';
            if (file.status === 'pending') {
                checksumHTML = `<span class="badge bg-secondary">En cours...</span>`;
            } else if (file.status === 'error') {
                checksumHTML = `<span class="badge bg-danger">Erreur</span>`;
            } else if (file.sha256) {
                checksumHTML = `<code class="small checksum-copy"
                                      data-full-checksum="${file.sha256}"
                                      title="Cliquer pour copier le checksum complet">
                                      ${file.sha256.substring(0, 12)}...
                                </code>`;
            }

            const fileBaseName = file.filename.substring(0, file.filename.lastIndexOf('.')) || file.filename;

            const row = `
                <tr>
                    <td><div class="truncate-text" title="${file.filename}">${file.filename}</div></td>
                    <td>${file.size_human}</td>
                    <td>${checksumHTML}</td>
                    <td>${new Date(file.created_at).toLocaleString('fr-FR')}</td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-info btn-copy-url" data-file-id="${file.id}" title="Copier l'URL">📋</button>
                        <button class="btn btn-sm btn-outline-warning btn-rename" data-file-id="${file.id}" data-filename="${fileBaseName}" title="Renommer">✏️</button>
                        <a href="/api/download/${file.id}" class="btn btn-sm btn-success" title="Télécharger">DL</a>
                        <button class="btn btn-sm btn-danger btn-delete" data-file-id="${file.id}" data-file-name="${file.filename}" title="Supprimer">X</button>
                    </td>
                </tr>
            `;
            fileTableBody.insertAdjacentHTML('beforeend', row);
        });
    };

    // --- Dropzone ---
    const initializeDropzone = async () => {
        try {
            const configResponse = await fetch('/api/public-config');
            if (!configResponse.ok) throw new Error('Could not fetch public config');
            const publicConfig = await configResponse.json();
            const maxFilesize = publicConfig.max_filesize_mb || 1024;

            const myDropzone = new Dropzone("#my-dropzone", {
                url: "/api/upload",
                autoProcessQueue: false,
                paramName: "file",
                maxFilesize: maxFilesize,
                parallelUploads: 20,

                // Options pour l'upload fractionné
                chunking: true,
                forceChunking: true,
                chunkSize: 5 * 1024 * 1024, // 5 Mo
                parallelChunkUploads: false, // Important pour les mauvaises connexions
                retryChunks: true,
                retryChunksLimit: 3,

                dictDefaultMessage: "Glissez-déposez des fichiers ici ou cliquez...",
                addRemoveLinks: true,
                dictCancelUpload: "Annuler",
                dictRemoveFile: "Retirer",

                init: function() {
                    const dropzoneInstance = this;
                    this.on("queuecomplete", function() {
                        fetchFiles();
                        dropzoneInstance.removeAllFiles();
                    });
                    this.on("error", function(file, response) {
                        const message = (typeof response === 'string') ? response : (response.error || "Erreur inconnue");
                        alert(`Erreur d'upload pour ${file.name}: ${message}`);
                        dropzoneInstance.removeFile(file);
                    });
                }
            });
            document.getElementById('upload-btn').addEventListener('click', () => myDropzone.processQueue());
        } catch (error) {
            console.error("Failed to initialize Dropzone:", error);
            document.querySelector("#my-dropzone .dz-message").textContent = "Erreur de configuration du module d'upload.";
        }
    };

    // --- Événements ---
    refreshBtn.addEventListener('click', fetchFiles);

    fileTableBody.addEventListener('click', async (e) => {
        const target = e.target;
        const actionButton = target.closest('button');

        if (actionButton) {
            const fileId = actionButton.dataset.fileId;
            if (actionButton.classList.contains('btn-delete')) {
                fileIdToDelete = fileId;
                fileToDeleteName.textContent = actionButton.dataset.fileName;
                deleteModal.show();
            } else if (actionButton.classList.contains('btn-rename')) {
                fileIdToRename = fileId;
                newFilenameInput.value = actionButton.dataset.filename;
                renameModal.show();
            } else if (actionButton.classList.contains('btn-copy-url')) {
                const url = `${window.location.origin}/api/download/${fileId}`;
                try {
                    await navigator.clipboard.writeText(url);
                    const originalText = actionButton.innerHTML;
                    actionButton.disabled = true;
                    actionButton.innerHTML = 'Copié !';
                    setTimeout(() => {
                        actionButton.innerHTML = originalText;
                        actionButton.disabled = false;
                     }, 1500);
                } catch (err) {
                    console.error('Erreur de copie: ', err);
                }
            }
        }

        if (target.classList.contains('checksum-copy')) {
            const fullChecksum = target.dataset.fullChecksum;
            if (fullChecksum) {
                try {
                    await navigator.clipboard.writeText(fullChecksum);
                    const originalText = target.innerHTML;
                    target.innerHTML = 'Copié !';
                    target.style.color = '#198754'; // Vert
                    setTimeout(() => {
                        target.innerHTML = originalText;
                        target.style.color = '';
                    }, 1500);
                } catch (err) {
                    console.error('Erreur de copie du checksum: ', err);
                }
            }
        }
    });

    confirmDeleteBtn.addEventListener('click', async () => {
        if (!fileIdToDelete) return;
        try {
            const response = await fetch(`/api/files/${fileIdToDelete}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('La suppression a échoué.');
            deleteModal.hide();
            fetchFiles();
        } catch(error) {
            console.error(error);
            alert('Une erreur est survenue.');
        }
    });

    confirmRenameBtn.addEventListener('click', async () => {
        if (!fileIdToRename) return;
        const newName = newFilenameInput.value.trim();
        if (!newName) {
            alert("Le nom ne peut pas être vide.");
            return;
        }
        try {
            const response = await fetch(`/api/files/${fileIdToRename}/rename`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_name: newName })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Erreur inconnue.");
            renameModal.hide();
            fetchFiles();
        } catch (error) {
            alert(`Erreur lors du renommage : ${error.message}`);
        }
    });

    // --- Initialisation ---
    fetchFiles();
    initializeDropzone();
});