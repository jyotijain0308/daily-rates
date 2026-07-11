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
const shipmentSelect = document.getElementById('shipmentSelect');
const videoPreviewSection = document.getElementById('videoPreviewSection');
const mp4Preview = document.getElementById('mp4Preview');
const previewDownloadBtn = document.getElementById('previewDownloadBtn');

let latestFilename = null;
let shipmentsByCountry = {};

generateBtn.addEventListener('click', generatePpt);
countrySelect.addEventListener('change', () => {
    populateShipmentOptions(countrySelect.value);
    updateGenerateState();
});
shipmentSelect.addEventListener('change', updateGenerateState);

loadStatus();

async function loadStatus() {
    try {
        const status = await API.getGenerationStatus();
        const { total_products, latest_generation, countries, shipments_by_country } = status.data;
        shipmentsByCountry = shipments_by_country || {};

        productCountInfo.textContent = `${total_products} product${total_products !== 1 ? 's' : ''} in database`;
        countrySelect.innerHTML = '<option value="">Select country</option>';
        (countries || []).forEach(country => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            countrySelect.appendChild(option);
        });
        countrySelect.disabled = total_products === 0;
        populateShipmentOptions(countrySelect.value);

        if (total_products > 0) {
            statusIcon.textContent = '✅';
            statusTitle.textContent = 'Ready to Generate';
            statusMessage.textContent = 'Select a country and shipment method, then generate an MP4 video.';
        } else {
            statusIcon.textContent = '📥';
            statusTitle.textContent = 'No Products Yet';
            statusMessage.textContent = 'Import products first to enable generation.';
        }
        updateGenerateState();

        if (latest_generation) {
            latestFilename = latest_generation.filename;
            showLatest(latest_generation);
            showMp4Preview(latest_generation.filename);
        }

        await loadHistory();
    } catch (err) {
        showError(err.message);
    }
}

async function generatePpt() {
    const selectedCountry = countrySelect.value;
    const selectedShipment = shipmentSelect.value;
    if (!selectedCountry || !selectedShipment) {
        showError('Select a country and shipment method first');
        return;
    }

    generateBtn.disabled = true;
    downloadBtn.style.display = 'none';
    progressWrap.style.display = 'block';
    statusIcon.textContent = '⏳';
    statusTitle.textContent = 'Generating...';
    statusMessage.textContent = 'Please wait while your presentation is being created.';

    animateProgress();

    try {
        const result = await API.generatePpt({
            country: selectedCountry,
            shipment_by: selectedShipment,
        });
        completeProgress();

        latestFilename = result.data.filename;
        statusIcon.textContent = '🎉';
        statusTitle.textContent = 'Generation Complete!';
        statusMessage.textContent = result.message;

        downloadBtn.style.display = 'inline-flex';
        downloadBtn.href = API.downloadUrl(result.data.filename);
        showMp4Preview(result.data.filename);

        latestSection.style.display = 'block';
        const files = result.data.files || [result.data];
        latestInfo.innerHTML = `
            <div><strong>Files:</strong> ${files.length}</div>
            <div><strong>Products:</strong> ${result.data.product_count}</div>
            <div><strong>Shipment by:</strong> ${escapeHtml(result.data.shipment_by || selectedShipment)}</div>
            <div class="table-wrap" style="margin-top: 1rem;">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Country</th>
                            <th>Format</th>
                            <th>Shipment by</th>
                            <th>Products</th>
                            <th>File</th>
                            <th>Preview</th>
                            <th>Download</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${files.map(file => `
                            <tr>
                                <td>${escapeHtml(file.country || 'Products')}</td>
                                <td>${escapeHtml((file.format || 'mp4').toUpperCase())}</td>
                                <td>${escapeHtml(file.shipment_by || selectedShipment)}</td>
                                <td>${file.product_count || '—'}</td>
                                <td>${escapeHtml(file.filename)}</td>
                                <td>${isMp4(file.filename) ? `<button type="button" class="btn btn-sm btn-secondary preview-file-btn" data-filename="${escapeHtml(file.filename)}">Preview</button>` : '—'}</td>
                                <td><a href="${API.downloadUrl(file.filename)}" class="btn btn-sm btn-secondary">Download</a></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        latestInfo.querySelectorAll('.preview-file-btn').forEach(btn => {
            btn.addEventListener('click', () => showMp4Preview(btn.dataset.filename));
        });

        showSuccess('MP4 generated successfully!');
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
    generateBtn.disabled = !countrySelect.value || !shipmentSelect.value || countrySelect.disabled || shipmentSelect.disabled;
    generateBtn.textContent = 'Generate MP4';
}

function populateShipmentOptions(country) {
    const shipments = country ? (shipmentsByCountry[country] || []) : [];
    shipmentSelect.innerHTML = '<option value="">Select shipment</option>';
    shipments.forEach(shipment => {
        const option = document.createElement('option');
        option.value = shipment;
        option.textContent = shipment;
        shipmentSelect.appendChild(option);
    });
    shipmentSelect.disabled = shipments.length === 0;
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

function showMp4Preview(filename) {
    if (!isMp4(filename)) {
        videoPreviewSection.style.display = 'none';
        mp4Preview.removeAttribute('src');
        mp4Preview.load();
        return;
    }

    const previewUrl = API.previewUrl(filename);
    const downloadUrl = API.downloadUrl(filename);
    videoPreviewSection.style.display = 'block';
    mp4Preview.src = previewUrl;
    previewDownloadBtn.href = downloadUrl;
}

function isMp4(filename) {
    return typeof filename === 'string' && filename.toLowerCase().endsWith('.mp4');
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
