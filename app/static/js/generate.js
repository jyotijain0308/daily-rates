const generateBtn = document.getElementById('generateBtn');
const downloadBtn = document.getElementById('downloadBtn');
const progressWrap = document.getElementById('progressWrap');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const statusTitle = document.getElementById('statusTitle');
const statusMessage = document.getElementById('statusMessage');
const statusIcon = document.getElementById('statusIcon');
const productCountInfo = document.getElementById('productCountInfo');
const latestSection = document.getElementById('latestSection');
const latestInfo = document.getElementById('latestInfo');
const historyWrap = document.getElementById('historyWrap');
const countrySelect = document.getElementById('countrySelect');
const formatSelect = document.getElementById('formatSelect');

let latestFilename = null;

generateBtn.addEventListener('click', generatePpt);
countrySelect.addEventListener('change', updateGenerateState);
formatSelect.addEventListener('change', updateGenerateState);

loadStatus();

async function loadStatus() {
    try {
        const status = await API.getGenerationStatus();
        const { total_products, latest_generation, countries } = status.data;

        productCountInfo.textContent = `${total_products} product${total_products !== 1 ? 's' : ''} in database`;
        countrySelect.innerHTML = '<option value="">Select country</option>';
        (countries || []).forEach(country => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        });
        countrySelect.disabled = total_products === 0;

        if (total_products > 0) {
            statusIcon.textContent = '✅';
            statusTitle.textContent = 'Ready to Generate';
            statusMessage.textContent = 'Select a country and format, then generate.';
        } else {
            statusIcon.textContent = '📥';
            statusTitle.textContent = 'No Products Yet';
            statusMessage.textContent = 'Import products first to enable generation.';
        }
        updateGenerateState();

        if (latest_generation) {
            latestFilename = latest_generation.filename;
            showLatest(latest_generation);
            downloadBtn.style.display = 'inline-flex';
            downloadBtn.href = API.downloadUrl(latest_generation.filename);
        }

        await loadHistory();
    } catch (err) {
        showError(err.message);
    }
}

async function generatePpt() {
    const selectedCountry = countrySelect.value;
    const selectedFormat = formatSelect.value;
    if (!selectedCountry) {
        showError('Select a country first');
        return;
    }

    generateBtn.disabled = true;
    progressWrap.style.display = 'block';
    statusIcon.textContent = '⏳';
    statusTitle.textContent = 'Generating...';
    statusMessage.textContent = 'Please wait while your presentation is being created.';

    animateProgress();

    try {
        const result = await API.generatePpt({
            country: selectedCountry,
            format: selectedFormat,
        });
        completeProgress();

        latestFilename = result.data.filename;
        statusIcon.textContent = '🎉';
        statusTitle.textContent = 'Generation Complete!';
        statusMessage.textContent = result.message;

        downloadBtn.style.display = 'inline-flex';
        downloadBtn.href = API.downloadUrl(result.data.filename);

        latestSection.style.display = 'block';
        const files = result.data.files || [result.data];
        latestInfo.innerHTML = `
            <div><strong>Files:</strong> ${files.length}</div>
            <div><strong>Products:</strong> ${result.data.product_count}</div>
            <div class="table-wrap" style="margin-top: 1rem;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Country</th>
                            <th>Format</th>
                            <th>Products</th>
                            <th>File</th>
                            <th>Download</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${files.map(file => `
                            <tr>
                                <td>${escapeHtml(file.country || 'Products')}</td>
                                <td>${escapeHtml((file.format || selectedFormat).toUpperCase())}</td>
                                <td>${file.product_count || '—'}</td>
                                <td>${escapeHtml(file.filename)}</td>
                                <td><a href="${API.downloadUrl(file.filename)}" class="btn btn-sm btn-secondary">Download</a></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        showSuccess(`${selectedFormat.toUpperCase()} generated successfully!`);
        await loadHistory();
    } catch (err) {
        statusIcon.textContent = '❌';
        statusTitle.textContent = 'Generation Failed';
        statusMessage.textContent = err.message;
        showError(err.message);
    } finally {
        updateGenerateState();
        setTimeout(() => {
            progressWrap.style.display = 'none';
            progressFill.style.width = '0%';
        }, 1000);
    }
}

function updateGenerateState() {
    generateBtn.disabled = !countrySelect.value || countrySelect.disabled;
    generateBtn.textContent = `Generate ${formatSelect.value.toUpperCase()}`;
}

function animateProgress() {
    let width = 0;
    progressFill.style.width = '0%';
    progressText.textContent = 'Fetching exchange rates...';

    const interval = setInterval(() => {
        width += Math.random() * 15;
        if (width > 90) {
            width = 90;
            clearInterval(interval);
        }
        progressFill.style.width = `${width}%`;

        if (width > 30 && width < 60) {
            progressText.textContent = 'Building product slides...';
        } else if (width >= 60) {
            progressText.textContent = 'Finalizing presentation...';
        }
    }, 300);

    generateBtn._progressInterval = interval;
}

function completeProgress() {
    if (generateBtn._progressInterval) {
        clearInterval(generateBtn._progressInterval);
    }
    progressFill.style.width = '100%';
    progressText.textContent = 'Done!';
}

function showLatest(info) {
    latestSection.style.display = 'block';
    latestInfo.innerHTML = `
        <div><strong>File:</strong> ${escapeHtml(info.filename)}</div>
        <div><strong>Generated:</strong> ${formatDate(info.generated_at)}</div>
        <div><strong>Products:</strong> ${info.product_count}</div>
    `;
}

async function loadHistory() {
    try {
        const result = await API.getGenerationHistory();
        const history = result.data;

        if (history.length === 0) {
            historyWrap.innerHTML = '<p class="empty-state">No generations yet</p>';
            return;
        }

        historyWrap.innerHTML = `
            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Filename</th>
                            <th>Products</th>
                            <th>Status</th>
                            <th>Generated</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${history.map(h => `
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
    } catch (err) {
        historyWrap.innerHTML = `<p class="empty-state">${err.message}</p>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
