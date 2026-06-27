const statsGrid = document.getElementById('statsGrid');
const historyTableWrap = document.getElementById('historyTableWrap');
const downloadAction = document.getElementById('downloadAction');
const generateActionHint = document.getElementById('generateActionHint');
const downloadActionHint = document.getElementById('downloadActionHint');

loadDashboard();

async function loadDashboard() {
    try {
        const [stats, status, history] = await Promise.all([
            API.getProductStats(),
            API.getGenerationStatus(),
            API.getGenerationHistory(),
        ]);

        const countryCount = Object.keys(stats.data.countries || {}).length;
        const latest = status.data.latest_generation;

        statsGrid.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${stats.data.total_products}</div>
                <div class="stat-label">Products</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${countryCount}</div>
                <div class="stat-label">Origin Countries</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${status.data.total_generations}</div>
                <div class="stat-label">Generations</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${latest ? '✓' : '—'}</div>
                <div class="stat-label">${latest ? formatDate(latest.generated_at) : 'No PPT yet'}</div>
            </div>
        `;

        if (stats.data.total_products > 0) {
            generateActionHint.textContent = `${stats.data.total_products} products ready`;
        } else {
            generateActionHint.textContent = 'Import products first';
        }

        if (latest) {
            downloadAction.style.display = 'block';
            downloadAction.href = API.downloadUrl(latest.filename);
            downloadActionHint.textContent = latest.filename;
        }

        renderHistory(history.data);
    } catch (err) {
        statsGrid.innerHTML = '<div class="stat-card"><div class="stat-value">!</div><div class="stat-label">Error loading</div></div>';
        historyTableWrap.innerHTML = `<p class="empty-state">${err.message}</p>`;
        showError(err.message);
    }
}

function renderHistory(history) {
    if (history.length === 0) {
        historyTableWrap.innerHTML = '<p class="empty-state">No presentations generated yet. Start by importing products.</p>';
        return;
    }

    historyTableWrap.innerHTML = `
        <div class="table-wrap">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Filename</th>
                        <th>Products</th>
                        <th>Status</th>
                        <th>Generated</th>
                        <th>Download</th>
                    </tr>
                </thead>
                <tbody>
                    ${history.slice(0, 10).map(h => `
                        <tr>
                            <td>${escapeHtml(h.filename)}</td>
                            <td>${h.product_count}</td>
                            <td><span class="badge badge-${h.status === 'success' ? 'success' : 'error'}">${h.status}</span></td>
                            <td>${formatDate(h.generated_at)}</td>
                            <td>${h.status === 'success' ? `<a href="${API.downloadUrl(h.filename)}" class="btn btn-sm btn-secondary">Download</a>` : '—'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
