// Désactive la recherche automatique de Dropzone.
Dropzone.autoDiscover = false;

document.addEventListener('DOMContentLoaded', function() {
    // --- STATE ---
    let currentFolderId = null;

    // --- ELEMENTS ---
    const itemTableBody = document.getElementById('item-table-body');
    const breadcrumbsList = document.getElementById('breadcrumbs-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const newFolderBtn = document.getElementById('new-folder-btn');
    const expirationValueInput = document.getElementById('expiration-value');
    const expirationUnitInput = document.getElementById('expiration-unit');
    let myDropzone;
    let maxExpirationMinutes = 0;

    // --- MODALS ---
    const deleteModal = new bootstrap.Modal(document.getElementById('delete-confirm-modal'));
    let itemToDelete = {};
    const renameModal = new bootstrap.Modal(document.getElementById('rename-modal'));
    let itemToRename = {};
    const newFolderModal = new bootstrap.Modal(document.getElementById('new-folder-modal'));

    // --- FETCH & RENDER ---
    const fetchAndRender = async (folderId = null) => {
        currentFolderId = folderId;
        const url = folderId ? `/api/items?parent_id=${folderId}` : '/api/items?parent_id=root';

        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '🔄 Chargement...';
        itemTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Chargement...</td></tr>`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Erreur réseau.');
            const data = await response.json();

            window.location.hash = folderId ? `/folder/${folderId}` : '';

            renderItems(data.items);
            renderBreadcrumbs(data.breadcrumbs);
        } catch (error) {
            console.error('Fetch error:', error);
            itemTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Impossible de charger les éléments.</td></tr>`;
        } finally {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '🔄 Rafraîchir';
        }
    };

    const renderItems = (items) => {
        itemTableBody.innerHTML = '';
        if (items.length === 0) {
            itemTableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Ce dossier est vide.</td></tr>`;
            return;
        }

        items.forEach(item => {
            const icon = item.item_type === 'directory' ? '📁' : '📄';
            const nameHtml = item.item_type === 'directory'
                ? `<a href="#" class="text-decoration-none folder-link" data-id="${item.id}">${item.name}</a>`
                : `<div class="truncate-text" title="${item.name}">${item.name}</div>`;

            const nameCellHtml = `
                <div class="d-flex align-items-center">
                    <span class="me-2">${icon}</span>
                    ${nameHtml}
                </div>
            `;

            let checksumHtml = '';
            if (item.item_type === 'file') {
                if (item.status === 'pending') checksumHtml = `<span class="badge bg-secondary">En cours...</span>`;
                else if (item.status === 'error') checksumHtml = `<span class="badge bg-danger">Erreur</span>`;
                else if (item.sha256) checksumHtml = `<code class="small checksum-copy" data-full-checksum="${item.sha256}" title="Cliquer pour copier">${item.sha256.substring(0, 12)}...</code>`;
            }

            const fileBaseName = (item.item_type === 'file' && item.name.includes('.')) ? item.name.substring(0, item.name.lastIndexOf('.')) : item.name;

            const actionsHtml = `
                <button class="btn btn-sm btn-outline-info btn-copy-url" data-id="${item.id}" data-type="${item.item_type}" title="Copier l'URL">📋</button>
                <button class="btn btn-sm btn-outline-warning btn-rename" data-id="${item.id}" data-name="${fileBaseName}" data-type="${item.item_type}" title="Renommer">✏️</button>
                ${item.item_type === 'file' ? `<a href="/api/download/${item.id}" class="btn btn-sm btn-success" title="Télécharger">DL</a>` : ''}
                <button class="btn btn-sm btn-danger btn-delete" data-id="${item.id}" data-name="${item.name}" title="Supprimer">X</button>
            `;

            const dateOptions = { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' };
            const createdAtHtml = new Date(item.created_at).toLocaleString('fr-FR', dateOptions);
            const expiresAtHtml = item.expires_at
                ? new Date(item.expires_at).toLocaleString('fr-FR', dateOptions)
                : '';

            const row = `
                <tr>
                    <td>${nameCellHtml}</td>
                    <td>${item.size_human || ''}</td>
                    <td>${checksumHtml}</td>
                    <td>${createdAtHtml}</td>
                    <td>${expiresAtHtml}</td>
                    <td class="text-end">${actionsHtml}</td>
                </tr>`;
            itemTableBody.insertAdjacentHTML('beforeend', row);
        });
    };

    const renderBreadcrumbs = (breadcrumbs) => {
        breadcrumbsList.innerHTML = `<li class="breadcrumb-item"><a href="#" class="folder-link" data-id="root">Racine</a></li>`;
        breadcrumbs.forEach((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;
            breadcrumbsList.insertAdjacentHTML('beforeend',
                `<li class="breadcrumb-item ${isLast ? 'active' : ''}" ${isLast ? 'aria-current="page"' : ''}>
                    ${isLast ? crumb.name : `<a href="#" class="folder-link" data-id="${crumb.id}">${crumb.name}</a>`}
                 </li>`
            );
        });
    };

    // --- ACTIONS ---
    const handleApiAction = async (url, options, successCallback) => {
        try {
            const response = await fetch(url, options);
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Erreur inconnue du serveur.');
            if(successCallback) successCallback(result);
        } catch (error) {
            alert(`Erreur: ${error.message}`);
        }
    };

    // --- DROPZONE ---
    const initializeDropzone = async () => {
        try {
            const configResponse = await fetch('/api/public-config');
            if (!configResponse.ok) throw new Error('Could not fetch public config');
            const publicConfig = await configResponse.json();

            maxExpirationMinutes = publicConfig.max_expiration_minutes;
            const defaultMinutes = publicConfig.default_expiration_minutes;

            if (defaultMinutes >= 1440 && defaultMinutes % 1440 === 0) {
                expirationValueInput.value = defaultMinutes / 1440;
                expirationUnitInput.value = 'days';
            } else if (defaultMinutes >= 60 && defaultMinutes % 60 === 0) {
                expirationValueInput.value = defaultMinutes / 60;
                expirationUnitInput.value = 'hours';
            } else {
                expirationValueInput.value = defaultMinutes;
                expirationUnitInput.value = 'minutes';
            }

            const maxFilesize = publicConfig.max_filesize_mb || 1024;
            const chunkSize = publicConfig.chunk_size_mb || 5;

            myDropzone = new Dropzone("#my-dropzone", {
                url: "/api/upload",
                previewTemplate: document.getElementById('dz-preview-template').innerHTML,
                autoProcessQueue: false,
                chunking: true,
                forceChunking: true,
                chunkSize: chunkSize * 1024 * 1024,
                parallelChunkUploads: false,
                retryChunks: true,
                retryChunksLimit: 3,
                maxFilesize: maxFilesize,
                parallelUploads: 20,
                addRemoveLinks: true,
                dictDefaultMessage: "Glissez-déposez des fichiers ou un dossier ici...",
                dictCancelUpload: "Annuler",
                dictRemoveFile: "Retirer",
                init: function() {
                    this.on('sending', (file, xhr, formData) => {
                        const unit = expirationUnitInput.value;
                        const value = parseInt(expirationValueInput.value, 10);
                        let totalMinutes = 0;

                        if (unit === 'minutes') totalMinutes = value;
                        else if (unit === 'hours') totalMinutes = value * 60;
                        else if (unit === 'days') totalMinutes = value * 60 * 24;

                        if (totalMinutes > maxExpirationMinutes) {
                            alert(`L'expiration ne peut pas dépasser ${maxExpirationMinutes} minutes.`);
                            this.cancelUpload(file);
                            return;
                        }

                        formData.append('parent_id', currentFolderId);
                        formData.append('expiration_minutes', totalMinutes);
                    });
                    this.on('queuecomplete', () => {
                        this.removeAllFiles(true);
                        setTimeout(() => {
                            fetchAndRender(currentFolderId);
                        }, 3000);
                    });
                    this.on("uploadprogress", function(file, progress) {
                        const progressText = file.previewElement.querySelector(".dz-progress-text");
                        if (progressText) {
                            progressText.textContent = Math.round(progress) + "%";
                        }
                    });
                    this.on("error", (file, response) => {
                        const message = (typeof response === 'string') ? response : (response.error || "Erreur inconnue");
                        alert(`Erreur d'upload pour ${file.name}: ${message}`);
                        this.removeFile(file);
                    });
                }
            });
            document.getElementById('upload-btn').addEventListener('click', () => myDropzone.processQueue());
        } catch(error) {
            console.error("Failed to initialize Dropzone:", error);
            document.querySelector("#my-dropzone .dz-message").textContent = "Erreur de configuration du module d'upload.";
        }
    };

    // --- EVENT LISTENERS ---
    refreshBtn.addEventListener('click', () => fetchAndRender(currentFolderId));

    document.body.addEventListener('click', async e => {
        const target = e.target;

        const folderLink = target.closest('.folder-link');
        if (folderLink) {
            e.preventDefault();
            const folderId = folderLink.dataset.id === 'root' ? null : folderLink.dataset.id;
            fetchAndRender(folderId);
        }

        const actionButton = target.closest('button');
        if (actionButton) {
            const itemId = actionButton.dataset.id;

            if (actionButton.matches('#new-folder-btn')) {
                document.getElementById('new-folder-name').value = '';
                newFolderModal.show();
            } else if (actionButton.matches('.btn-delete')) {
                itemToDelete = { id: itemId, name: actionButton.dataset.name };
                document.getElementById('item-to-delete-name').textContent = itemToDelete.name;
                deleteModal.show();
            } else if (actionButton.matches('.btn-rename')) {
                itemToRename = { id: itemId, name: actionButton.dataset.name, type: actionButton.dataset.type };
                document.getElementById('rename-title').textContent = `Renommer ${itemToRename.type === 'directory' ? 'le dossier' : 'le fichier'}`;
                document.getElementById('new-item-name').value = itemToRename.name;
                document.getElementById('rename-label').textContent = `Nouveau nom ${itemToRename.type === 'file' ? '(l\'extension sera conservée)' : ''} :`;
                renameModal.show();
            } else if (actionButton.matches('.btn-copy-url')) {
                const itemType = actionButton.dataset.type;
                let urlToCopy;
                if (itemType === 'directory') {
                    urlToCopy = `${window.location.origin}${window.location.pathname}#/folder/${itemId}`;
                } else {
                    urlToCopy = `${window.location.origin}/api/download/${itemId}`;
                }
                try {
                    await navigator.clipboard.writeText(urlToCopy);
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
                navigator.clipboard.writeText(fullChecksum).then(() => {
                    const originalText = target.innerHTML;
                    target.innerHTML = 'Copié !';
                    target.style.color = '#198754';
                    setTimeout(() => {
                        target.innerHTML = originalText;
                        target.style.color = '';
                    }, 1500);
                }).catch(err => console.error('Erreur de copie du checksum: ', err));
            }
        }
    });

    // --- MODAL CONFIRMATION LISTENERS ---
    document.getElementById('confirm-new-folder-btn').addEventListener('click', () => {
        const name = document.getElementById('new-folder-name').value.trim();
        if (name) {
            handleApiAction('/api/directories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, parent_id: currentFolderId })
            }, () => {
                newFolderModal.hide();
                fetchAndRender(currentFolderId);
            });
        }
    });

    document.getElementById('confirm-delete-btn').addEventListener('click', () => {
        handleApiAction(`/api/items/${itemToDelete.id}`, { method: 'DELETE' }, () => {
            deleteModal.hide();
            fetchAndRender(currentFolderId);
        });
    });

    document.getElementById('confirm-rename-btn').addEventListener('click', () => {
        const newName = document.getElementById('new-item-name').value.trim();
        if (newName) {
            handleApiAction(`/api/items/${itemToRename.id}/rename`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName })
            }, () => {
                renameModal.hide();
                fetchAndRender(currentFolderId);
            });
        }
    });

    // --- INITIALIZATION ---
    const handleInitialLoad = () => {
        const hash = window.location.hash;
        if (hash && hash.startsWith('#/folder/')) {
            const folderId = hash.substring('#/folder/'.length);
            fetchAndRender(folderId);
        } else {
            fetchAndRender(null);
        }
    };

    initializeDropzone();
    handleInitialLoad();
});