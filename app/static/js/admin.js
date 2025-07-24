document.addEventListener('DOMContentLoaded', function() {
    const loginSection = document.getElementById('login-section');
    const adminPanel = document.getElementById('admin-panel');
    const loginForm = document.getElementById('admin-login-form');
    const passwordInput = document.getElementById('admin-password');
    const loginError = document.getElementById('login-error');

    const configForm = document.getElementById('config-form');
    const maxUploadInput = document.getElementById('max-upload-mb');

    const logsTableBody = document.getElementById('logs-table-body');
    const logsPagination = document.getElementById('logs-pagination');

    const checkAuth = () => {
        const token = sessionStorage.getItem('admin-token');
        if (token) {
            loginSection.classList.add('d-none');
            adminPanel.classList.remove('d-none');
            loadAdminData();
        }
    };

    const loadAdminData = () => {
        fetchConfig();
        fetchLogs();
    };

    const getAuthHeader = () => {
        const token = sessionStorage.getItem('admin-token');
        return {
            'Content-Type': 'application/json',
            'X-Admin-Password': token
        };
    };

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = passwordInput.value;
        try {
            const response = await fetch('/admin/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            if (response.ok) {
                sessionStorage.setItem('admin-token', password);
                checkAuth();
            } else {
                const errorData = await response.json();
                loginError.textContent = errorData.error || 'Erreur d\'authentification.';
                loginError.classList.remove('d-none');
            }
        } catch (error) {
            loginError.textContent = 'Erreur de connexion au serveur.';
            loginError.classList.remove('d-none');
        }
    });

    const fetchConfig = async () => {
        try {
            const response = await fetch('/admin/config', { headers: getAuthHeader() });
            if (!response.ok) throw new Error('Erreur de chargement de la config.');
            const config = await response.json();
            maxUploadInput.value = config.max_upload_mb;
        } catch (error) {
            console.error(error);
            alert("Impossible de charger la configuration.");
        }
    };

    configForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newMaxSize = maxUploadInput.value;
        try {
            const response = await fetch('/admin/config', {
                method: 'POST',
                headers: getAuthHeader(),
                body: JSON.stringify({ max_upload_mb: newMaxSize })
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "Erreur inconnue");
            alert("Configuration enregistrée avec succès !");
            fetchConfig();
        } catch (error) {
            alert(`Erreur : ${error.message}`);
        }
    });

    const fetchLogs = async (page = 1) => {
        try {
            const response = await fetch(`/admin/logs?page=${page}`, { headers: getAuthHeader() });
            if (!response.ok) throw new Error('Erreur de chargement des logs.');
            const data = await response.json();
            logsTableBody.innerHTML = '';
            data.logs.forEach(log => {
                const row = `
                    <tr>
                        <td><small>${new Date(log.timestamp).toLocaleString('fr-FR')}</small></td>
                        <td><span class="badge bg-info">${log.action}</span></td>
                        <td>${log.details}</td>
                    </tr>
                `;
                logsTableBody.insertAdjacentHTML('beforeend', row);
            });
            renderPagination(data.total_pages, data.current_page);
        } catch (error) {
            console.error(error);
            logsTableBody.innerHTML = `<tr><td colspan="3" class="text-center text-danger">Impossible de charger les logs.</td></tr>`;
        }
    };

    const renderPagination = (totalPages, currentPage) => {
        logsPagination.innerHTML = '';
        for (let i = 1; i <= totalPages; i++) {
            const liClass = i === currentPage ? 'page-item active' : 'page-item';
            const pageItem = `<li class="${liClass}"><a class="page-link" href="#" data-page="${i}">${i}</a></li>`;
            logsPagination.insertAdjacentHTML('beforeend', pageItem);
        }
    };

    logsPagination.addEventListener('click', (e) => {
        e.preventDefault();
        if (e.target.tagName === 'A') {
            const page = e.target.dataset.page;
            if (page) {
                fetchLogs(page);
            }
        }
    });

    // --- Gestion de la Purge des Fichiers ---
    const confirmPurgeFilesBtn = document.getElementById('confirm-purge-files-btn');
    const purgeFilesModalEl = document.getElementById('purge-files-modal');
    if (purgeFilesModalEl && confirmPurgeFilesBtn) {
        const purgeFilesModal = new bootstrap.Modal(purgeFilesModalEl);
        confirmPurgeFilesBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/admin/purge', { method: 'POST', headers: getAuthHeader() });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Erreur inconnue.');
                alert(result.message);
                purgeFilesModal.hide();
                fetchLogs();
            } catch (error) {
                alert(`Erreur lors de la purge : ${error.message}`);
            }
        });
    }

    // --- Gestion de la Purge des Logs ---
    const confirmPurgeLogsBtn = document.getElementById('confirm-purge-logs-btn');
    const purgeLogsModalEl = document.getElementById('purge-logs-modal');
    if (purgeLogsModalEl && confirmPurgeLogsBtn) {
        const purgeLogsModal = new bootstrap.Modal(purgeLogsModalEl);
        confirmPurgeLogsBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/admin/logs/purge', { method: 'POST', headers: getAuthHeader() });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Erreur inconnue.');
                alert(result.message);
                purgeLogsModal.hide();
                fetchLogs();
            } catch (error) {
                alert(`Erreur lors de la purge des logs: ${error.message}`);
            }
        });
    }

    // Vérifier l'authentification au chargement de la page
    checkAuth();
});