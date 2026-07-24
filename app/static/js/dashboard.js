const statsGrid = document.getElementById('statsGrid');
const socialConnectionsCard = document.getElementById('socialConnectionsCard');
const updatedProductsCard = document.getElementById('updatedProductsCard');
const activeJobsCard = document.getElementById('activeJobsCard');
const todayGenerationsCard = document.getElementById('todayGenerationsCard');
const downloadAction = document.getElementById('downloadAction');
const generateActionHint = document.getElementById('generateActionHint');
const downloadActionHint = document.getElementById('downloadActionHint');
const dashboardShareModal = document.getElementById('shareModal');
const closeDashboardShareModalBtn = document.getElementById('closeShareModalBtn');
const dashboardShareFileName = document.getElementById('shareFileName');
const dashboardSharePostTitle = document.getElementById('sharePostTitle');
const dashboardSharePostDescription = document.getElementById('sharePostDescription');
const dashboardSharePostVisibility = document.getElementById('sharePostVisibility');
const dashboardShareDownloadBtn = document.getElementById('shareDownloadBtn');
const dashboardGenerateHashtagsBtn = document.getElementById('generateHashtagsBtn');
const dashboardHashtagGeneratorStatus = document.getElementById('hashtagGeneratorStatus');
const dashboardCopyShareCaptionBtn = document.getElementById('copyShareCaptionBtn');
const dashboardCopyShareLinkBtn = document.getElementById('copyShareLinkBtn');
let dashboardShareFile = null;
let dashboardShareLink = '';
let dashboardCompanySettings = null;

const dashboardSharePlatforms = [
    { key: 'youtube', label: 'YouTube', statusMethod: 'getYouTubeStatus', publishMethod: 'publishYouTube', statusEl: document.getElementById('shareYouTubeStatus'), buttonEl: document.getElementById('publishYouTubeBtn'), messageEl: document.getElementById('youtubePublishMessage'), buttonText: 'Publish to YouTube', setupMessage: 'Set YouTube OAuth keys in .env, then connect YouTube in Company settings.', disconnectedMessage: 'Connect YouTube in Company settings first.', titleLimit: 100, extraPayload: () => ({ privacy_status: dashboardSharePostVisibility.value }) },
    { key: 'facebook', label: 'Facebook Page', statusMethod: 'getFacebookStatus', publishMethod: 'publishFacebook', statusEl: document.getElementById('shareFacebookStatus'), buttonEl: document.getElementById('publishFacebookBtn'), messageEl: document.getElementById('facebookPublishMessage'), buttonText: 'Publish to Facebook Page', setupMessage: 'Set Facebook app keys in .env, then connect Facebook in Company settings.', disconnectedMessage: 'Connect Facebook in Company settings first.' },
    { key: 'instagram', label: 'Instagram', statusMethod: 'getInstagramStatus', publishMethod: 'publishInstagram', statusEl: document.getElementById('shareInstagramStatus'), buttonEl: document.getElementById('publishInstagramBtn'), messageEl: document.getElementById('instagramPublishMessage'), buttonText: 'Publish to Instagram', setupMessage: 'Set SOCIAL_PUBLIC_BASE_URL and connect a linked Instagram account.', disconnectedMessage: 'Connect Facebook Page with Instagram in Company settings first.', isReady: status => Boolean(status.facebook_connected && status.public_base_url_configured && status.connected) },
    { key: 'x', label: 'X', statusMethod: 'getXStatus', publishMethod: 'publishX', statusEl: document.getElementById('shareXStatus'), buttonEl: document.getElementById('publishXBtn'), messageEl: document.getElementById('xPublishMessage'), buttonText: 'Publish to X', setupMessage: 'Set X app keys in .env, then connect X in Company settings.', disconnectedMessage: 'Connect X in Company settings first.' },
    { key: 'linkedin_personal', label: 'LinkedIn Profile', statusMethod: 'getLinkedInPersonalStatus', publishMethod: 'publishLinkedInPersonal', statusEl: document.getElementById('shareLinkedInPersonalStatus'), buttonEl: document.getElementById('publishLinkedInPersonalBtn'), messageEl: document.getElementById('linkedinPersonalPublishMessage'), buttonText: 'Publish to LinkedIn Profile', setupMessage: 'Set LinkedIn app keys in .env, then connect LinkedIn personal profile in Company settings.', disconnectedMessage: 'Connect LinkedIn personal profile in Company settings first.', titleLimit: 200, extraPayload: () => ({ visibility: dashboardSharePostVisibility.value === 'public' ? 'PUBLIC' : 'CONNECTIONS' }) },
    { key: 'linkedin_page', label: 'LinkedIn Page', statusMethod: 'getLinkedInPageStatus', publishMethod: 'publishLinkedInPage', statusEl: document.getElementById('shareLinkedInStatus'), buttonEl: document.getElementById('publishLinkedInBtn'), messageEl: document.getElementById('linkedinPublishMessage'), buttonText: 'Publish to LinkedIn Page', setupMessage: 'Set LinkedIn app keys in .env, then connect LinkedIn Page in Company settings.', disconnectedMessage: 'Connect LinkedIn Page in Company settings first.', titleLimit: 200, extraPayload: () => ({ visibility: dashboardSharePostVisibility.value === 'public' ? 'PUBLIC' : 'CONNECTIONS' }) },
];

closeDashboardShareModalBtn.addEventListener('click', closeDashboardShareModal);
dashboardShareModal.addEventListener('click', event => {
    if (event.target === dashboardShareModal) closeDashboardShareModal();
});
dashboardCopyShareCaptionBtn.addEventListener('click', () => copyDashboardShareText(dashboardSharePostDescription.value, 'Description copied'));
dashboardCopyShareLinkBtn.addEventListener('click', () => copyDashboardShareText(dashboardShareLink, 'Link copied'));
dashboardGenerateHashtagsBtn.addEventListener('click', generateDashboardHashtagsForShare);
dashboardSharePlatforms.forEach(platform => {
    platform.buttonEl.addEventListener('click', () => publishDashboardShare(platform));
});
loadDashboard();

async function loadDashboard() {
    try {
        const [stats, status] = await Promise.all([
            API.getProductStats(),
            API.getGenerationStatus(),
        ]);

        const countryCount = stats.data.total_countries ?? Object.keys(stats.data.countries || {}).length;
        const latest = status.data.latest_generation;
        const connectedPlatforms = status.data.connected_social_platform_details || [];
        const totalGenerations = status.data.total_generations ?? 0;

        statsGrid.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${stats.data.total_products}</div>
                <div class="stat-label">Products</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${countryCount}</div>
                <div class="stat-label">Origin Countries</div>
            </div>
            ${renderSimpleStatCard(totalGenerations, 'Total Generations')}
            ${renderDateStatCard('Latest MP4', latest?.generated_at, 'No MP4 yet')}
            ${renderDateStatCard('Last Import', status.data.last_import_at, 'No import yet')}
        `;

        renderActiveJobsCard(
            status.data.active_generation_job_details || [],
            status.data.active_generation_jobs || 0
        );
        renderSocialConnectionsCard(connectedPlatforms, status.data.connected_social_platform_count ?? connectedPlatforms.length);
        renderUpdatedProductsCard(
            status.data.updated_products_today || [],
            status.data.products_updated_today || 0,
            status.data.large_rate_changes_today || 0,
            status.data.large_rate_change_products_today || [],
            status.data.updated_products_rate_summary || {}
        );
        renderTodayGenerationsCard(
            status.data.today_generation_history || [],
            status.data.today_generations || 0,
            status.data.today_success_generations || 0,
            status.data.today_failed_generations || 0
        );

        if (stats.data.total_products > 0) {
            generateActionHint.textContent = `${stats.data.total_products} products ready`;
        } else {
            generateActionHint.textContent = 'Import products first';
        }

        if (latest) {
            downloadAction.style.display = 'block';
            downloadAction.href = API.downloadUrl(latest.filename);
            downloadActionHint.textContent = 'Latest MP4 is ready';
            downloadActionHint.title = latest.filename;
        }

    } catch (err) {
        statsGrid.innerHTML = '<div class="stat-card"><div class="stat-value">!</div><div class="stat-label">Error loading</div></div>';
        activeJobsCard.innerHTML = `<p class="empty-state">${err.message}</p>`;
        updatedProductsCard.innerHTML = `<p class="empty-state">${err.message}</p>`;
        todayGenerationsCard.innerHTML = `<p class="empty-state">${err.message}</p>`;
        showError(err.message);
    }
}

function renderSocialConnectionsCard(platforms, total) {
    const allPlatforms = [
        { provider: 'youtube', label: 'YouTube', icon: 'YT' },
        { provider: 'facebook', label: 'Facebook', icon: 'f' },
        { provider: 'instagram', label: 'Instagram', icon: 'IG' },
        { provider: 'linkedin_page', label: 'LinkedIn Page', icon: 'in' },
        { provider: 'linkedin_personal', label: 'LinkedIn', icon: 'in' },
        { provider: 'x', label: 'X', icon: 'X' },
    ];
    const connected = new Set(platforms.map(platform => platform.provider));

    socialConnectionsCard.innerHTML = `
        <div class="card-header-row">
            <div>
                <h2>Social Media Connections</h2>
                <p class="subtitle">${total} connected channel${total !== 1 ? 's' : ''} available for MP4 publishing.</p>
            </div>
            <a class="btn btn-secondary btn-sm" href="/company">Manage</a>
        </div>
        <div class="social-platform-grid">
            ${allPlatforms.map(platform => {
                const isConnected = connected.has(platform.provider);
                return `
                    <div class="social-platform-card ${isConnected ? 'connected' : 'inactive'}" data-tooltip="${escapeHtml(platform.label)}">
                        <span class="social-platform-icon-wrap">
                            <span class="social-platform-icon social-${platform.provider}">${escapeHtml(platform.icon)}</span>
                            ${isConnected ? '<span class="social-platform-check" aria-label="Connected">✓</span>' : ''}
                        </span>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderDateStatCard(label, isoString, emptyText) {
    if (!isoString) {
        return `
            <div class="stat-card stat-date-card">
                <div class="stat-date-empty">${escapeHtml(emptyText)}</div>
                <div class="stat-label">${escapeHtml(label)}</div>
            </div>
        `;
    }

    const date = new Date(isoString);
    return `
        <div class="stat-card stat-date-card">
            <div class="stat-date-main">${date.toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
            })}</div>
            <div class="stat-date-sub">${date.toLocaleTimeString('en-IN', {
                hour: '2-digit',
                minute: '2-digit',
            })}</div>
            <div class="stat-label">${escapeHtml(label)}</div>
        </div>
    `;
}

function renderSimpleStatCard(value, label) {
    return `
        <div class="stat-card">
            <div class="stat-value">${escapeHtml(value)}</div>
            <div class="stat-label">${escapeHtml(label)}</div>
        </div>
    `;
}

function renderActiveJobsCard(jobs, total) {
    if (total === 0) {
        activeJobsCard.innerHTML = `
            <div class="card-header-row">
                <div>
                    <h2>Pending/Running Jobs</h2>
                    <p class="subtitle">No active MP4 generation jobs right now.</p>
                </div>
                <span class="badge badge-success">0 active</span>
            </div>
        `;
        return;
    }

    activeJobsCard.innerHTML = `
        <div class="card-header-row">
            <div>
                <h2>Pending/Running Jobs</h2>
                <p class="subtitle">${total} active job${total !== 1 ? 's' : ''}.</p>
            </div>
            <a class="btn btn-secondary btn-sm" href="/generate">Open Generator</a>
        </div>
        <div class="table-wrap">
            <table class="data-table compact-data-table">
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Country / Shipment</th>
                        <th>Total Products</th>
                        <th>Updated</th>
                    </tr>
                </thead>
                <tbody>
                    ${jobs.map(job => `
                        <tr>
                            <td><span class="badge badge-${job.status === 'running' ? 'warning' : 'secondary'}">${escapeHtml(job.status || '-')}</span></td>
                            <td>${formatCountryShipment(job.country, job.shipment_by)}</td>
                            <td>${escapeHtml(job.product_count ?? 0)}</td>
                            <td class="job-updated">${formatSingleLineDateTime(job.updated_at)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderUpdatedProductsCard(products, total, largeRateChanges, largeProducts = [], rateSummary = {}) {
    if (total === 0) {
        updatedProductsCard.innerHTML = `
            <div class="card-header-row">
                <div>
                    <h2>Products Updated Today</h2>
                    <p class="subtitle">No product rates were updated today.</p>
                </div>
            </div>
            ${renderUpdatedProductsSummary(rateSummary, total)}
        `;
        return;
    }

    updatedProductsCard.innerHTML = `
        <div class="card-header-row">
            <div>
                <h2>Products Updated Today</h2>
                <p class="subtitle">Today&apos;s products stats summary.</p>
            </div>
            <a class="btn btn-secondary btn-sm" href="/products">View Products</a>
        </div>
        ${renderUpdatedProductsSummary(rateSummary, total)}
    `;
}

function renderUpdatedProductsSummary(summary, total) {
    const items = [
        { label: 'Products', value: summary.total ?? total ?? 0, className: 'products' },
        { label: 'Increased', value: summary.increased || 0, className: 'increased', icon: '↑' },
        { label: 'Decreased', value: summary.decreased || 0, className: 'decreased', icon: '↓' },
        { label: 'No Change', value: summary.no_change ?? Math.max((summary.total ?? total ?? 0) - (summary.increased || 0) - (summary.decreased || 0), 0), className: 'no-change' },
    ];
    return `
        <div class="updated-products-summary-grid" aria-label="Today's products stats summary">
            ${items.map(item => `
                <div class="updated-products-summary-card ${item.className}">
                    <strong>${escapeHtml(item.value)}</strong>
                    <span>${item.icon ? `<b aria-hidden="true">${item.icon}</b>` : ''}${escapeHtml(item.label)}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function formatCompactDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return `
        <span class="generated-date">${date.toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
        })}</span>
        <span class="generated-time">${date.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
        })}</span>
    `;
}

function formatSingleLineDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function renderTodayGenerationsCard(todayHistory, total, success, failed) {
    const successfulHistory = todayHistory.filter(item => item.status === 'success');

    if (successfulHistory.length === 0) {
        todayGenerationsCard.innerHTML = `
            <div class="card-header-row">
                <div>
                    <h2>Today Generations</h2>
                    <p class="subtitle">No successful videos generated today.</p>
                </div>
                ${renderTodayGenerationSummary(total, success, failed)}
            </div>
        `;
        return;
    }

    todayGenerationsCard.innerHTML = `
        <div class="card-header-row">
            <div>
                <h2>Today Generations</h2>
                <p class="subtitle">${success} successful generation${success !== 1 ? 's' : ''} today. Showing latest ${Math.min(successfulHistory.length, 20)}.</p>
            </div>
            ${renderTodayGenerationSummary(total, success, failed)}
        </div>
        ${renderTodayGenerationTable(successfulHistory.slice(0, 20))}
    `;
    bindDashboardShareButtons();
}

function renderTodayGenerationSummary(total, success, failed) {
    return `
        <div class="today-generation-summary">
            <div>
                <strong>${escapeHtml(total)}</strong>
                <span>Total</span>
            </div>
            <div>
                <strong>${escapeHtml(success)} / ${escapeHtml(total)}</strong>
                <span>Success</span>
            </div>
            <div>
                <strong>${escapeHtml(failed)} / ${escapeHtml(total)}</strong>
                <span>Failed</span>
            </div>
        </div>
    `;
}

function renderTodayGenerationTable(history) {
    const showReason = history.some(h => h.error_message);
    return `
        <div class="table-wrap">
            <table class="data-table compact-data-table today-generation-table">
                <thead>
                    <tr>
                        <th>Country / Shipment</th>
                        <th>Total Products</th>
                        <th>Share Status</th>
                        <th>Actions</th>
                        ${showReason ? '<th>Reason</th>' : ''}
                    </tr>
                </thead>
                <tbody>
                    ${history.map(h => `
                        <tr>
                            <td>${formatCountryShipment(h.country, h.shipment_by)}</td>
                            <td>${h.product_count}</td>
                            <td>${renderGenerationShareStatus(h.share_statuses || [])}</td>
                            <td>${renderTodayGenerationActions(h)}</td>
                            ${showReason ? `<td class="generation-reason">${escapeHtml(h.error_message || '-')}</td>` : ''}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function formatCountryShipment(country, shipment) {
    const countryText = country || '-';
    const shipmentText = shipment || '-';
    return `
        <span class="country-shipment-cell">
            <strong>${escapeHtml(countryText)}</strong>
            <small>${escapeHtml(shipmentText)}</small>
        </span>
    `;
}

function renderGenerationShareStatus(statuses) {
    if (!statuses.length) {
        return '<span class="share-status-empty">Not shared</span>';
    }

    const published = statuses
        .filter(item => item.status === 'published')
        .map(item => compactSharePlatformLabel(item.label));
    const failed = statuses
        .filter(item => item.status === 'failed')
        .map(item => compactSharePlatformLabel(item.label));
    const pending = statuses
        .filter(item => item.status !== 'published' && item.status !== 'failed')
        .map(item => compactSharePlatformLabel(item.label));

    return `
        <div class="share-status-summary">
            ${published.length ? `<div class="share-status-line published"><strong>Published</strong><span>${escapeHtml(published.join(', '))}</span></div>` : ''}
            ${failed.length ? `<div class="share-status-line failed"><strong>Failed</strong><span>${escapeHtml(failed.join(', '))}</span></div>` : ''}
            ${pending.length ? `<div class="share-status-line pending"><strong>Pending</strong><span>${escapeHtml(pending.join(', '))}</span></div>` : ''}
        </div>
    `;
}

function compactSharePlatformLabel(label) {
    return String(label || '')
        .replace(/^Direct\s+/i, '')
        .replace(/\s+Personal\s*$/i, '')
        .replace(/\s+Profile\s*$/i, '')
        .replace(/\s+Page\s*$/i, '')
        .trim() || 'Social';
}

function renderTodayGenerationActions(generation) {
    if (generation.status !== 'success' || !generation.filename) {
        return '-';
    }

    return `
        <div class="file-action-row dashboard-generation-actions">
            <a href="${API.downloadUrl(generation.filename)}" class="icon-action-btn" aria-label="Download MP4" title="Download MP4">
                ${iconDownload()}
            </a>
            <button
                type="button"
                class="icon-action-btn dashboard-share-btn"
                aria-label="Share MP4"
                title="Share MP4"
                data-filename="${escapeHtml(generation.filename)}"
                data-country="${escapeHtml(generation.country || '')}"
                data-shipment="${escapeHtml(generation.shipment_by || '')}"
                data-products="${escapeHtml(generation.product_count || '')}"
            >${iconShare()}</button>
        </div>
    `;
}

function iconDownload() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 17v3h14v-3" />
        </svg>
    `;
}

function iconShare() {
    return `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path d="M8 12h8m0 0-3-3m3 3-3 3M5 5h14v14H5z" />
        </svg>
    `;
}

function bindDashboardShareButtons() {
    todayGenerationsCard.querySelectorAll('.dashboard-share-btn').forEach(button => {
        button.addEventListener('click', () => openDashboardShareModal({
            filename: button.dataset.filename,
            country: button.dataset.country,
            shipment_by: button.dataset.shipment,
            product_count: button.dataset.products,
        }));
    });
}

async function openDashboardShareModal(file) {
    if (!file?.filename) return;

    dashboardShareFile = await enrichDashboardShareFile(file);
    dashboardShareLink = new URL(API.previewUrl(dashboardShareFile.filename), window.location.origin).href;
    dashboardShareFileName.textContent = dashboardShareFile.filename;
    dashboardSharePostTitle.value = buildDashboardShareTitle(dashboardShareFile);
    dashboardSharePostDescription.value = await dashboardDefaultSocialPostDescription();
    dashboardSharePostVisibility.value = 'private';
    dashboardShareDownloadBtn.href = API.downloadUrl(dashboardShareFile.filename);
    dashboardHashtagGeneratorStatus.textContent = '';
    resetDashboardSharePublishState();
    dashboardShareModal.style.display = 'flex';
    await refreshDashboardShareStatuses();
}

function closeDashboardShareModal() {
    dashboardShareModal.style.display = 'none';
    dashboardShareFile = null;
    dashboardShareLink = '';
}

async function enrichDashboardShareFile(file) {
    try {
        const result = await API.getGenerationShareMetadata(file.filename);
        return { ...file, ...(result.data || {}) };
    } catch (err) {
        console.warn('Could not load MP4 share metadata', err);
        return file;
    }
}

async function dashboardDefaultSocialPostDescription() {
    if (!dashboardCompanySettings) {
        try {
            const result = await API.getCurrentCompany();
            dashboardCompanySettings = result.data?.settings || {};
        } catch (err) {
            dashboardCompanySettings = {};
        }
    }
    return (dashboardCompanySettings.social_post_description || '').trim();
}

function buildDashboardShareTitle(file) {
    const country = (file.country || 'Products').trim();
    return `${country} | AL AWEER MARKET DUBAI WHOLESALE PRICE ${formatDashboardShareDate()} | FRUITS & VEGETABLES`.slice(0, 255);
}

function formatDashboardShareDate() {
    return new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        timeZone: 'Asia/Dubai',
    }).format(new Date()).toUpperCase();
}

function resetDashboardSharePublishState() {
    dashboardSharePlatforms.forEach(platform => {
        platform.statusEl.textContent = 'Checking';
        platform.statusEl.className = 'status-pill status-inactive';
        platform.messageEl.textContent = 'Checking connection...';
        platform.buttonEl.disabled = true;
        platform.buttonEl.textContent = platform.buttonText;
    });
}

async function refreshDashboardShareStatuses() {
    await Promise.all([
        ...dashboardSharePlatforms.map(refreshDashboardPlatformStatus),
    ]);
}

async function refreshDashboardPlatformStatus(platform) {
    try {
        const result = await API[platform.statusMethod]();
        const status = result.data || {};
        const configured = status.configured !== false;
        const ready = platform.isReady ? platform.isReady(status) : Boolean(status.connected);
        if (!configured) {
            setPlatformState(platform, 'Setup needed', platform.setupMessage, false);
            return;
        }
        if (!ready) {
            setPlatformState(platform, 'Not connected', status.message || platform.disconnectedMessage, false);
            return;
        }
        setPlatformState(
            platform,
            'Connected',
            status.external_account_name ? `Ready for ${status.external_account_name}.` : `Ready for ${platform.label}.`,
            true,
        );
    } catch (err) {
        setPlatformState(platform, 'Error', err.message, false);
    }
}

function setPlatformState(platform, statusText, message, enabled) {
    platform.statusEl.textContent = statusText;
    platform.statusEl.className = `status-pill ${enabled ? 'status-active' : 'status-inactive'}`;
    platform.messageEl.textContent = message;
    platform.buttonEl.disabled = !enabled;
}

async function publishDashboardShare(platform) {
    if (!dashboardShareFile?.filename) return;
    const title = dashboardSharePostTitle.value.trim().slice(0, platform.titleLimit || 255);
    if (!title) {
        showError(`${platform.label} title is required`);
        return;
    }

    platform.buttonEl.disabled = true;
    platform.buttonEl.textContent = platform.successVerb === 'Uploaded to' ? 'Uploading...' : 'Publishing...';
    platform.messageEl.textContent = `${platform.successVerb || 'Publishing to'} ${platform.label}. Keep this page open.`;

    try {
        const result = await API[platform.publishMethod]({
            filename: dashboardShareFile.filename,
            title,
            description: dashboardSharePostDescription.value.trim(),
            ...(platform.extraPayload ? platform.extraPayload() : {}),
        });
        const url = result.data?.external_post_url;
        platform.messageEl.innerHTML = url
            ? `${platform.successVerb || 'Published to'} ${platform.label}: <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`
            : result.message || `${platform.successVerb || 'Published to'} ${platform.label}`;
        showSuccess(result.message || `${platform.successVerb || 'Published to'} ${platform.label}`);
        await loadDashboard();
    } catch (err) {
        platform.messageEl.textContent = err.message;
        showError(err.message);
        platform.buttonEl.disabled = false;
    } finally {
        platform.buttonEl.textContent = platform.buttonText;
    }
}

async function generateDashboardHashtagsForShare() {
    if (!dashboardShareFile?.filename) return;

    dashboardGenerateHashtagsBtn.disabled = true;
    dashboardGenerateHashtagsBtn.textContent = 'Generating...';

    try {
        const result = await API.generateSocialHashtags({
            title: dashboardSharePostTitle.value.trim(),
            country: dashboardShareFile.country || '',
            shipment_by: dashboardShareFile.shipment_by || '',
            products: dashboardShareFile.product_names || [],
            platform: 'social',
            count: 30,
        });
        const hashtags = result.data?.text || '';
        if (!hashtags) {
            throw new Error('No hashtags were generated.');
        }
        dashboardSharePostDescription.value = replaceDashboardDescriptionHashtags(
            dashboardSharePostDescription.value,
            hashtags,
        );
        dashboardHashtagGeneratorStatus.textContent = 'Hashtags added to the description.';
        showSuccess('Hashtags added to description');
    } catch (err) {
        dashboardHashtagGeneratorStatus.textContent = `Hashtag generation failed: ${err.message}`;
        showError(err.message);
    } finally {
        dashboardGenerateHashtagsBtn.disabled = false;
        dashboardGenerateHashtagsBtn.textContent = 'Generate AI Hashtags';
    }
}

function replaceDashboardDescriptionHashtags(description, hashtags) {
    const cleanHashtags = String(hashtags || '')
        .split(/\s+/)
        .map(tag => tag.trim())
        .filter(tag => tag.startsWith('#') && tag.length > 1)
        .join(' ');
    const withoutGeneratedSection = String(description || '')
        .replace(/\n{2,}Generated hashtags:\n#[\s\S]*$/i, '')
        .replace(/\n{2,}(?:#[^\n]+\s*)+$/i, '')
        .trim();
    return `${withoutGeneratedSection}\n\nGenerated hashtags:\n${cleanHashtags}`.trim();
}

async function copyDashboardShareText(text, message) {
    try {
        await navigator.clipboard.writeText(text || '');
        showSuccess(message);
    } catch (err) {
        showError('Could not copy to clipboard');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
