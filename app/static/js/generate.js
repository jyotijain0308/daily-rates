const generateBtn = document.getElementById('generateBtn');
const cancelGenerateBtn = document.getElementById('cancelGenerateBtn');
const previewBtn = document.getElementById('previewBtn');
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
const previewShareBtn = document.getElementById('previewShareBtn');
const backgroundAudioInput = document.getElementById('backgroundAudioInput');
const backgroundAudioSelect = document.getElementById('backgroundAudioSelect');
const browseBackgroundAudioBtn = document.getElementById('browseBackgroundAudioBtn');
const clearBackgroundAudioBtn = document.getElementById('clearBackgroundAudioBtn');
const backgroundAudioFileName = document.getElementById('backgroundAudioFileName');
const backgroundAudioPreview = document.getElementById('backgroundAudioPreview');
const backgroundAudioRightsRow = document.getElementById('backgroundAudioRightsRow');
const backgroundAudioRights = document.getElementById('backgroundAudioRights');
const shareModal = document.getElementById('shareModal');
const duplicateGenerationModal = document.getElementById('duplicateGenerationModal');
const closeDuplicateGenerationModalBtn = document.getElementById('closeDuplicateGenerationModalBtn');
const cancelDuplicateGenerationBtn = document.getElementById('cancelDuplicateGenerationBtn');
const forceDuplicateGenerationBtn = document.getElementById('forceDuplicateGenerationBtn');
const duplicateExistingFile = document.getElementById('duplicateExistingFile');
const closeShareModalBtn = document.getElementById('closeShareModalBtn');
const shareFileName = document.getElementById('shareFileName');
const sharePostTitle = document.getElementById('sharePostTitle');
const sharePostDescription = document.getElementById('sharePostDescription');
const sharePostVisibility = document.getElementById('sharePostVisibility');
const generateHashtagsBtn = document.getElementById('generateHashtagsBtn');
const hashtagGeneratorStatus = document.getElementById('hashtagGeneratorStatus');
const copyShareCaptionBtn = document.getElementById('copyShareCaptionBtn');
const copyShareLinkBtn = document.getElementById('copyShareLinkBtn');
const shareDownloadBtn = document.getElementById('shareDownloadBtn');
const sharePlatformGrid = document.getElementById('sharePlatformGrid');
const shareYouTubeStatus = document.getElementById('shareYouTubeStatus');
const publishYouTubeBtn = document.getElementById('publishYouTubeBtn');
const youtubePublishMessage = document.getElementById('youtubePublishMessage');
const shareFacebookStatus = document.getElementById('shareFacebookStatus');
const publishFacebookBtn = document.getElementById('publishFacebookBtn');
const facebookPublishMessage = document.getElementById('facebookPublishMessage');
const shareInstagramStatus = document.getElementById('shareInstagramStatus');
const publishInstagramBtn = document.getElementById('publishInstagramBtn');
const instagramPublishMessage = document.getElementById('instagramPublishMessage');
const shareXStatus = document.getElementById('shareXStatus');
const publishXBtn = document.getElementById('publishXBtn');
const xPublishMessage = document.getElementById('xPublishMessage');
const shareLinkedInPersonalStatus = document.getElementById('shareLinkedInPersonalStatus');
const publishLinkedInPersonalBtn = document.getElementById('publishLinkedInPersonalBtn');
const linkedinPersonalPublishMessage = document.getElementById('linkedinPersonalPublishMessage');
const shareLinkedInStatus = document.getElementById('shareLinkedInStatus');
const publishLinkedInBtn = document.getElementById('publishLinkedInBtn');
const linkedinPublishMessage = document.getElementById('linkedinPublishMessage');

let latestFilename = null;
let shipmentsByCountry = {};
let activeJobId = null;
let jobPollTimer = null;
let selectedBackgroundAudioFile = null;
let reusableAudio = [];
let previewFilename = null;
let currentShareFile = null;
let currentShareLink = '';
let currentCompanySettings = null;
let pendingDuplicateGeneration = null;
let initialShareHandled = false;

const EASTERN_FARMS_DESCRIPTION_TEMPLATE = `Fresh Fruits & Vegetables at Eastern Farms LLC.

Follow Us:

Facebook - @easternfarms
Instagram - @easternfarmsllc
LinkedIn - @easternfarmsllc
Twitter - @easternfarmsllc

Co-Founder & MD Nitin Dixit: linkedin.com/in/nitin-dixit-7239b9135

Founder & CEO Bhawana Jain: linkedin.com/in/writingownstory

Membership: / @easternfarmsllc

Check out The Right Way to Start Your Export to Dubai, a guide by our CEO. Grab it on:
Amazon | Barnes & Noble | Waterstones

Visit our website https://easternfarmsllc.com/ for more information on how we can help you in the import/export of fresh fruits and vegetables, cereals, rice, wheat flour / maida, spices to UAE and other countries.

Eastern Farms L.L.C, Dubai, UAE
Located at: Office #1835, One by Omniyat, Business Bay, Dubai

Mobile: +971586204123
E-mail: trade@easternfarmsllc.com

Join this channel to get access to perks:
   / @easternfarmsllc`;

generateBtn.addEventListener('click', () => generatePpt());
cancelGenerateBtn.addEventListener('click', cancelGeneration);
previewBtn.addEventListener('click', () => {
    if (latestFilename) showMp4Preview(latestFilename, true);
});
closeDuplicateGenerationModalBtn.addEventListener('click', closeDuplicateGenerationModal);
cancelDuplicateGenerationBtn.addEventListener('click', closeDuplicateGenerationModal);
forceDuplicateGenerationBtn.addEventListener('click', forcePendingDuplicateGeneration);
duplicateGenerationModal.addEventListener('click', (e) => {
    if (e.target === duplicateGenerationModal) closeDuplicateGenerationModal();
});
browseBackgroundAudioBtn.addEventListener('click', () => backgroundAudioInput.click());
clearBackgroundAudioBtn.addEventListener('click', clearBackgroundAudio);
backgroundAudioInput.addEventListener('change', handleBackgroundAudioSelected);
backgroundAudioSelect.addEventListener('change', handleExistingAudioSelected);
previewShareBtn.addEventListener('click', () => {
    if (previewFilename) openSharePanel({ filename: previewFilename });
});
closeShareModalBtn.addEventListener('click', closeSharePanel);
shareModal.addEventListener('click', (e) => {
    if (e.target === shareModal) closeSharePanel();
});
copyShareCaptionBtn.addEventListener('click', () => copyText(commonPostDescription(), 'Description copied'));
copyShareLinkBtn.addEventListener('click', () => copyText(currentShareLink, 'Link copied'));
generateHashtagsBtn.addEventListener('click', generateAIHashtagsForShare);
publishYouTubeBtn.addEventListener('click', publishCurrentFileToYouTube);
publishFacebookBtn.addEventListener('click', publishCurrentFileToFacebook);
publishInstagramBtn.addEventListener('click', publishCurrentFileToInstagram);
publishXBtn.addEventListener('click', publishCurrentFileToX);
publishLinkedInPersonalBtn.addEventListener('click', publishCurrentFileToLinkedInPersonal);
publishLinkedInBtn.addEventListener('click', publishCurrentFileToLinkedIn);
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
            if (isMp4(latestFilename)) {
                previewBtn.style.display = 'inline-flex';
            }
            showLatest(latest_generation);
            showMp4Preview(latest_generation.filename);
        }

        await loadReusableAudio();
        await loadHistory();
        await openInitialSharePanel();
    } catch (err) {
        showError(err.message);
    }
}

async function generatePpt(force = false) {
    const selectedCountry = countrySelect.value;
    const selectedShipment = shipmentSelect.value;
    if (!selectedCountry || !selectedShipment) {
        showError('Select a country and shipment method first');
        return;
    }

    generateBtn.disabled = true;
    cancelGenerateBtn.style.display = 'inline-flex';
    previewBtn.style.display = 'none';
    downloadBtn.style.display = 'none';
    progressWrap.style.display = 'block';
    statusIcon.textContent = '⏳';
    statusTitle.textContent = 'Generating...';
    statusMessage.textContent = 'Please wait while your MP4 video is being created.';

    animateProgress();

    try {
        let audioPath = null;
        let audioId = backgroundAudioSelect.value || null;
        if (selectedBackgroundAudioFile) {
            if (!backgroundAudioRights.checked) {
                throw new Error('Confirm that you own or have licensed rights to the selected audio.');
            }
            statusMessage.textContent = 'Uploading background audio...';
            const audioResult = await API.uploadGenerationAudio(selectedBackgroundAudioFile, true);
            audioId = audioResult.data.id;
            await loadReusableAudio(audioId);
        }

        const result = await API.generatePpt({
            country: selectedCountry,
            shipment_by: selectedShipment,
            audio_path: audioPath,
            audio_id: audioId,
            force,
        });
        activeJobId = result.data.job_id;
        statusMessage.textContent = result.message;
        pollGenerationJob(activeJobId, selectedShipment);
    } catch (err) {
        if (isDuplicateGenerationWarning(err) && !force) {
            resetGenerationUiAfterDuplicateWarning();
            openDuplicateGenerationModal(err);
            return;
        }
        statusIcon.textContent = '❌';
        statusTitle.textContent = 'Generation Failed';
        statusMessage.textContent = err.message;
        showError(err.message);
    }
}

function isDuplicateGenerationWarning(err) {
    return err?.status === 409 && err?.data?.status === 'duplicate';
}

function resetGenerationUiAfterDuplicateWarning() {
    if (generateBtn._progressInterval) {
        clearInterval(generateBtn._progressInterval);
    }
    generateBtn.disabled = false;
    cancelGenerateBtn.style.display = 'none';
    progressWrap.style.display = 'none';
    progressFill.style.width = '0%';
    statusIcon.textContent = '⚠️';
    statusTitle.textContent = 'Duplicate MP4 Found';
    statusMessage.textContent = 'An identical MP4 already exists for this country, shipment, date, products, images, and rates.';
}

function openDuplicateGenerationModal(err) {
    const existing = err.data?.data?.existing_generation;
    const criteria = err.data?.data?.fingerprint_criteria || {};
    pendingDuplicateGeneration = {
        country: countrySelect.value,
        shipment_by: shipmentSelect.value,
        existing,
        criteria,
    };
    duplicateExistingFile.innerHTML = `
        <div><strong>Existing file:</strong> ${escapeHtml(existing?.filename || 'Generated MP4')}</div>
        <div><strong>Country:</strong> ${escapeHtml(criteria.country || pendingDuplicateGeneration.country || '-')}</div>
        <div><strong>Shipment:</strong> ${escapeHtml(criteria.shipment_by || pendingDuplicateGeneration.shipment_by || '-')}</div>
        <div><strong>Date:</strong> ${escapeHtml(criteria.generation_date || '-')}</div>
        <div><strong>Products:</strong> ${escapeHtml(criteria.product_count ?? '-')}</div>
    `;
    duplicateGenerationModal.style.display = 'flex';
}

function closeDuplicateGenerationModal() {
    duplicateGenerationModal.style.display = 'none';
    pendingDuplicateGeneration = null;
}

function forcePendingDuplicateGeneration() {
    if (!pendingDuplicateGeneration) return;
    duplicateGenerationModal.style.display = 'none';
    pendingDuplicateGeneration = null;
    generatePpt(true);
}

function handleBackgroundAudioSelected(e) {
    const file = e.target.files[0];
    if (!file) {
        clearBackgroundAudio();
        return;
    }

    if (!file.type.startsWith('audio/')) {
        showError('Please select an audio file');
        clearBackgroundAudio();
        return;
    }

    selectedBackgroundAudioFile = file;
    backgroundAudioSelect.value = '';
    backgroundAudioFileName.textContent = file.name;
    clearBackgroundAudioBtn.style.display = 'inline-flex';
    backgroundAudioRightsRow.style.display = 'inline-flex';
    backgroundAudioRights.checked = false;
    backgroundAudioPreview.removeAttribute('src');
    backgroundAudioPreview.style.display = 'none';
}

function clearBackgroundAudio() {
    selectedBackgroundAudioFile = null;
    backgroundAudioInput.value = '';
    backgroundAudioSelect.value = '';
    backgroundAudioFileName.textContent = 'No audio selected';
    clearBackgroundAudioBtn.style.display = 'none';
    backgroundAudioRights.checked = false;
    backgroundAudioRightsRow.style.display = 'none';
    backgroundAudioPreview.pause();
    backgroundAudioPreview.removeAttribute('src');
    backgroundAudioPreview.style.display = 'none';
}

async function loadReusableAudio(selectedId = '') {
    try {
        const result = await API.getGenerationAudio();
        reusableAudio = result.data || [];
        backgroundAudioSelect.innerHTML = '<option value="">No background audio</option>';
        reusableAudio.forEach(audio => {
            const option = document.createElement('option');
            option.value = String(audio.id);
            option.textContent = audio.original_filename;
            backgroundAudioSelect.appendChild(option);
        });
        if (selectedId) {
            backgroundAudioSelect.value = String(selectedId);
            handleExistingAudioSelected();
        }
    } catch (err) {
        console.warn('Could not load background audio', err);
    }
}

function handleExistingAudioSelected() {
    selectedBackgroundAudioFile = null;
    backgroundAudioInput.value = '';
    backgroundAudioRights.checked = false;
    backgroundAudioRightsRow.style.display = 'none';

    const selected = reusableAudio.find(audio => String(audio.id) === backgroundAudioSelect.value);
    if (!selected) {
        backgroundAudioFileName.textContent = 'No audio selected';
        clearBackgroundAudioBtn.style.display = 'none';
        backgroundAudioPreview.pause();
        backgroundAudioPreview.removeAttribute('src');
        backgroundAudioPreview.style.display = 'none';
        return;
    }

    backgroundAudioFileName.textContent = selected.original_filename;
    clearBackgroundAudioBtn.style.display = 'inline-flex';
    backgroundAudioPreview.src = selected.audio_url;
    backgroundAudioPreview.style.display = 'block';
}

async function pollGenerationJob(jobId, selectedShipment) {
    clearTimeout(jobPollTimer);
    try {
        const result = await API.getGenerationJob(jobId);
        const job = result.data;
        statusMessage.textContent = job.message || 'Generating MP4...';

        if (job.status === 'completed') {
            completeProgress();
            activeJobId = null;
            cancelGenerateBtn.style.display = 'none';
            updateGenerateState();
            setTimeout(() => {
                progressWrap.style.display = 'none';
                progressFill.style.width = '0%';
            }, 1000);
            handleGenerationComplete(job.result, selectedShipment);
            return;
        }

        if (job.status === 'cancelled') {
            activeJobId = null;
            cancelGenerateBtn.style.display = 'none';
            progressWrap.style.display = 'none';
            progressFill.style.width = '0%';
            statusIcon.textContent = '⏹';
            statusTitle.textContent = 'Generation Cancelled';
            statusMessage.textContent = job.message || 'MP4 generation was cancelled.';
            updateGenerateState();
            showWarning('MP4 generation cancelled');
            return;
        }

        if (job.status === 'failed') {
            activeJobId = null;
            cancelGenerateBtn.style.display = 'none';
            progressWrap.style.display = 'none';
            progressFill.style.width = '0%';
            statusIcon.textContent = '❌';
            statusTitle.textContent = 'Generation Failed';
            statusMessage.textContent = job.error || job.message || 'Generation failed';
            updateGenerateState();
            showError(statusMessage.textContent);
            return;
        }

        jobPollTimer = setTimeout(() => pollGenerationJob(jobId, selectedShipment), 2000);
    } catch (err) {
        statusIcon.textContent = '❌';
        statusTitle.textContent = 'Generation Status Failed';
        statusMessage.textContent = err.message;
        cancelGenerateBtn.style.display = 'none';
        updateGenerateState();
        showError(err.message);
    }
}

async function cancelGeneration() {
    if (!activeJobId) return;

    cancelGenerateBtn.disabled = true;
    try {
        await API.cancelGenerationJob(activeJobId);
        statusMessage.textContent = 'Cancellation requested...';
    } catch (err) {
        showError(err.message);
    } finally {
        cancelGenerateBtn.disabled = false;
    }
}

async function handleGenerationComplete(data, selectedShipment) {
    latestFilename = data.filename;
    statusIcon.textContent = '🎉';
    statusTitle.textContent = 'Generation Complete!';
    statusMessage.textContent = 'MP4 generated successfully.';

    downloadBtn.style.display = 'inline-flex';
    downloadBtn.href = API.downloadUrl(data.filename);
    if (isMp4(data.filename)) {
        previewBtn.style.display = 'inline-flex';
    }
    showMp4Preview(data.filename);

    latestSection.style.display = 'block';
    const files = data.files || [data];
    latestInfo.innerHTML = `
        <div><strong>Files:</strong> ${files.length}</div>
        <div><strong>Products:</strong> ${data.product_count}</div>
        <div><strong>Shipment by:</strong> ${escapeHtml(data.shipment_by || selectedShipment)}</div>
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
                        <th>Share</th>
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
                            <td>${isMp4(file.filename) ? previewButton(file) : '—'}</td>
                            <td>${isMp4(file.filename) ? shareButton(file) : '—'}</td>
                            <td><a href="${API.downloadUrl(file.filename)}" class="btn btn-sm btn-secondary">Download</a></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    bindPreviewButtons(latestInfo);
    bindShareButtons(latestInfo);

    showSuccess('MP4 generated successfully!');
    await loadHistory();
}

function updateGenerateState() {
    generateBtn.disabled = Boolean(activeJobId) || !countrySelect.value || !shipmentSelect.value || countrySelect.disabled || shipmentSelect.disabled;
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
            progressText.textContent = 'Finalizing MP4 video...';
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
        ${isMp4(info.filename) ? `<div class="file-action-row">${previewButton(info)}<button type="button" class="btn btn-sm btn-secondary share-file-btn" data-filename="${escapeHtml(info.filename)}" data-products="${info.product_count || ''}">Share</button><a href="${API.downloadUrl(info.filename)}" class="btn btn-sm btn-secondary">Download</a></div>` : ''}
    `;
    bindPreviewButtons(latestInfo);
    bindShareButtons(latestInfo);
}

function showMp4Preview(filename, shouldScroll = false) {
    if (!isMp4(filename)) {
        videoPreviewSection.style.display = 'none';
        mp4Preview.removeAttribute('src');
        mp4Preview.load();
        previewFilename = null;
        return;
    }

    const previewUrl = API.previewUrl(filename);
    const downloadUrl = API.downloadUrl(filename);
    videoPreviewSection.style.display = 'block';
    mp4Preview.src = previewUrl;
    previewDownloadBtn.href = downloadUrl;
    previewFilename = filename;
    if (shouldScroll) {
        videoPreviewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function isMp4(filename) {
    return typeof filename === 'string' && filename.toLowerCase().endsWith('.mp4');
}

function formatDateTimeStack(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    return `
        <span class="generated-date">${date.toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
        })}</span>
        <span class="generated-time">${date.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
        })}</span>
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
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${history.map(h => `
                            <tr>
                                <td>${escapeHtml(h.filename)}</td>
                                <td>${h.product_count}</td>
                                <td><span class="badge badge-${h.status === 'success' ? 'success' : 'error'}">${h.status}</span></td>
                                <td>${formatDateTimeStack(h.generated_at)}</td>
                                <td>${h.status === 'success' ? `<div class="file-action-row">${isMp4(h.filename) ? previewButton(h) + shareButton(h) : ''}<a href="${API.downloadUrl(h.filename)}" class="btn btn-sm btn-secondary">Download</a></div>` : '—'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        bindPreviewButtons(historyWrap);
        bindShareButtons(historyWrap);
    } catch (err) {
        historyWrap.innerHTML = `<p class="empty-state">${err.message}</p>`;
    }
}

function previewButton(file) {
    return `<button type="button" class="btn btn-sm btn-secondary preview-file-btn" data-filename="${escapeHtml(file.filename)}">Preview</button>`;
}

function shareButton(file) {
    return `
        <button
            type="button"
            class="btn btn-sm btn-secondary share-file-btn"
            data-filename="${escapeHtml(file.filename)}"
            data-country="${escapeHtml(file.country || '')}"
            data-shipment="${escapeHtml(file.shipment_by || '')}"
            data-products="${file.product_count || ''}"
        >Share</button>
    `;
}

function bindPreviewButtons(root) {
    root.querySelectorAll('.preview-file-btn').forEach(btn => {
        btn.addEventListener('click', () => showMp4Preview(btn.dataset.filename, true));
    });
}

function bindShareButtons(root) {
    root.querySelectorAll('.share-file-btn').forEach(btn => {
        btn.addEventListener('click', () => openSharePanel({
            filename: btn.dataset.filename,
            country: btn.dataset.country,
            shipment_by: btn.dataset.shipment,
            product_count: btn.dataset.products,
        }));
    });
}

async function openSharePanel(file) {
    if (!file?.filename) return;

    file = withShareFileMetadata(file);
    file = await enrichShareFileMetadata(file);
    currentShareFile = file;
    const link = new URL(API.previewUrl(file.filename), window.location.origin).href;
    const titleParts = [
        file.country,
        file.shipment_by ? `${file.shipment_by} shipment` : '',
        'daily product rates',
    ].filter(Boolean);
    const title = buildSocialTitle(file);
    const description = await defaultSocialPostDescription();

    shareFileName.textContent = file.filename;
    sharePostTitle.value = title;
    sharePostDescription.value = `${description}\n\n${buildDefaultHashtags(file)}`;
    sharePostVisibility.value = 'private';
    hashtagGeneratorStatus.textContent = '';
    currentShareLink = link;
    youtubePublishMessage.textContent = 'Checking YouTube connection...';
    publishYouTubeBtn.disabled = true;
    facebookPublishMessage.textContent = 'Checking Facebook connection...';
    publishFacebookBtn.disabled = true;
    instagramPublishMessage.textContent = 'Checking Instagram connection...';
    publishInstagramBtn.disabled = true;
    xPublishMessage.textContent = 'Checking X connection...';
    publishXBtn.disabled = true;
    linkedinPersonalPublishMessage.textContent = 'Checking LinkedIn personal profile connection...';
    publishLinkedInPersonalBtn.disabled = true;
    linkedinPublishMessage.textContent = 'Checking LinkedIn connection...';
    publishLinkedInBtn.disabled = true;
    shareDownloadBtn.href = API.downloadUrl(file.filename);
    renderSharePlatformButtons(commonPostDescription(), link);
    shareModal.style.display = 'flex';
    await refreshShareYouTubeStatus();
    await refreshShareFacebookStatus();
    await refreshShareInstagramStatus();
    await refreshShareXStatus();
    await refreshShareLinkedInPersonalStatus();
    await refreshShareLinkedInStatus();
}

async function openInitialSharePanel() {
    if (initialShareHandled) return;
    initialShareHandled = true;

    const params = new URLSearchParams(window.location.search);
    const filename = params.get('share');
    if (!filename) return;

    await openSharePanel({ filename });
    videoPreviewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function defaultSocialPostDescription() {
    const settings = await loadCurrentCompanySettingsForShare();
    return (settings?.social_post_description || '').trim() || EASTERN_FARMS_DESCRIPTION_TEMPLATE;
}

async function loadCurrentCompanySettingsForShare() {
    if (currentCompanySettings) {
        return currentCompanySettings;
    }

    try {
        const result = await API.getCurrentCompany();
        currentCompanySettings = result.data?.settings || {};
    } catch (err) {
        console.warn('Could not load company social post defaults', err);
        currentCompanySettings = {};
    }
    return currentCompanySettings;
}

function closeSharePanel() {
    shareModal.style.display = 'none';
    currentShareFile = null;
    currentShareLink = '';
}

function renderSharePlatformButtons(caption, link) {
    sharePlatformGrid.innerHTML = '';
}

function buildSocialTitle(file) {
    const country = shareFileCountry(file) || 'Products';
    const title = `${country} | AL AWEER MARKET DUBAI WHOLESALE PRICE ${formatShareDate()} | FRUITS & VEGETABLES`;
    return title.slice(0, 255);
}

function buildDefaultHashtags(file) {
    const country = shareFileCountry(file);
    const shipmentBy = file.shipment_by || '';
    const staticTags = [
        '#wholesaleprices2025',
        '#freshvegetablesdubai',
        '#import',
        '#export',
        '#alaweermarket',
        '#easternfarmsllc',
        '#dubaiimporters',
        '#bhawanajain',
        '#nitindixit',
        '#vegetablepricesdubai',
    ];
    const dynamicTags = [
        country,
        shipmentBy,
    ].map(toHashtag).filter(Boolean);
    return [...new Set([...staticTags, ...dynamicTags])].join(' ');
}

function toHashtag(value) {
    const normalized = String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
    return normalized ? `#${normalized}` : '';
}

function withShareFileMetadata(file) {
    return {
        ...file,
        country: shareFileCountry(file),
    };
}

async function enrichShareFileMetadata(file) {
    if (Array.isArray(file.product_names) && file.product_names.length > 0) {
        return file;
    }

    try {
        const result = await API.getGenerationShareMetadata(file.filename);
        const metadata = result.data || {};
        return withShareFileMetadata({
            ...file,
            ...metadata,
            product_names: metadata.product_names || file.product_names || [],
        });
    } catch (err) {
        console.warn('Could not load MP4 product metadata for sharing', err);
        return file;
    }
}

function shareFileCountry(file) {
    return (file?.country || inferCountryFromFilename(file?.filename) || '').trim();
}

function inferCountryFromFilename(filename) {
    if (!filename) return '';

    const fileSlug = filename
        .replace(/\.[^.]+$/, '')
        .replace(/_products_price_list_\d+$/i, '');
    const countries = Array.from(countrySelect.options)
        .map(option => option.value)
        .filter(Boolean)
        .sort((a, b) => b.length - a.length);

    return countries.find(country => {
        const slug = slugifySharePart(country);
        return fileSlug === slug || fileSlug.startsWith(`${slug}_`);
    }) || '';
}

function slugifySharePart(value) {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
}

function formatShareDate() {
    const parts = new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        timeZone: 'Asia/Dubai',
    }).formatToParts(new Date());
    const day = parts.find(part => part.type === 'day')?.value || '';
    const month = parts.find(part => part.type === 'month')?.value || '';
    const year = parts.find(part => part.type === 'year')?.value || '';
    return `${day} ${month} ${year}`.trim().toUpperCase();
}

function commonPostTitle(limit = 255) {
    return sharePostTitle.value.trim().slice(0, limit);
}

function commonPostDescription() {
    return sharePostDescription.value.trim();
}

async function generateAIHashtagsForShare() {
    if (!currentShareFile?.filename) return;

    generateHashtagsBtn.disabled = true;
    generateHashtagsBtn.textContent = 'Generating...';

    try {
        const result = await API.generateSocialHashtags({
            title: commonPostTitle(),
            country: shareFileCountry(currentShareFile),
            shipment_by: currentShareFile.shipment_by || '',
            products: currentShareFile.product_names || [],
            platform: 'social',
            count: 30,
        });
        const hashtags = result.data?.text || '';
        if (!hashtags) {
            throw new Error('No hashtags were generated.');
        }
        sharePostDescription.value = replaceDescriptionHashtags(sharePostDescription.value, hashtags);
        renderSharePlatformButtons(commonPostDescription(), currentShareLink);
        const hashtagCount = countHashtags(hashtags);
        if (result.data?.source === 'ollama') {
            hashtagGeneratorStatus.textContent = `AI hashtags generated with local Ollama. Added ${hashtagCount} hashtags to the description.`;
            showSuccess('AI hashtags added to description');
        } else {
            hashtagGeneratorStatus.textContent = `Local AI model is not available. Added ${hashtagCount} fallback hashtags to the description. Start Ollama to use AI generation.`;
            showWarning('Ollama unavailable; fallback hashtags used');
        }
    } catch (err) {
        hashtagGeneratorStatus.textContent = `AI hashtag generation failed: ${err.message}`;
        showError(err.message);
    } finally {
        generateHashtagsBtn.disabled = false;
        generateHashtagsBtn.textContent = 'Generate AI Hashtags';
    }
}

function replaceDescriptionHashtags(description, hashtags) {
    const cleanHashtags = normalizeHashtagText(hashtags);
    const withoutGeneratedSection = String(description || '')
        .replace(/\n{2,}Generated hashtags:\n#[\s\S]*$/i, '')
        .replace(/\n{2,}(?:#[^\n]+\s*)+$/i, '')
        .trim();
    return `${withoutGeneratedSection}\n\nGenerated hashtags:\n${cleanHashtags}`.trim();
}

function normalizeHashtagText(hashtags) {
    return String(hashtags || '')
        .split(/\s+/)
        .map(tag => tag.trim())
        .filter(tag => tag.startsWith('#') && tag.length > 1)
        .join(' ');
}

function countHashtags(hashtags) {
    const matches = normalizeHashtagText(hashtags).match(/#[a-z0-9_]+/gi);
    return matches ? matches.length : 0;
}

function youtubePrivacyStatus() {
    const value = sharePostVisibility.value;
    return ['private', 'unlisted', 'public'].includes(value) ? value : 'private';
}

function linkedInVisibility() {
    return sharePostVisibility.value === 'public' ? 'PUBLIC' : 'CONNECTIONS';
}

async function refreshShareYouTubeStatus() {
    try {
        const result = await API.getYouTubeStatus();
        const status = result.data || {};
        if (!status.configured) {
            shareYouTubeStatus.textContent = 'Setup needed';
            shareYouTubeStatus.className = 'status-pill status-inactive';
            youtubePublishMessage.textContent = 'Set YouTube OAuth keys in .env, then connect YouTube in Company settings.';
            publishYouTubeBtn.disabled = true;
            return;
        }
        if (!status.connected) {
            shareYouTubeStatus.textContent = 'Not connected';
            shareYouTubeStatus.className = 'status-pill status-inactive';
            youtubePublishMessage.textContent = 'Connect YouTube in Company settings first.';
            publishYouTubeBtn.disabled = true;
            return;
        }

        shareYouTubeStatus.textContent = 'Connected';
        shareYouTubeStatus.className = 'status-pill status-active';
        youtubePublishMessage.textContent = status.external_account_name
            ? `Ready to publish to ${status.external_account_name}.`
            : 'Ready to publish to YouTube.';
        publishYouTubeBtn.disabled = false;
    } catch (err) {
        shareYouTubeStatus.textContent = 'Error';
        shareYouTubeStatus.className = 'status-pill status-inactive';
        youtubePublishMessage.textContent = err.message;
        publishYouTubeBtn.disabled = true;
    }
}

async function publishCurrentFileToYouTube() {
    if (!currentShareFile?.filename) return;

    const title = commonPostTitle(100);
    if (!title) {
        showError('YouTube title is required');
        return;
    }

    publishYouTubeBtn.disabled = true;
    publishYouTubeBtn.textContent = 'Publishing...';
    youtubePublishMessage.textContent = 'Uploading MP4 to YouTube. Keep this page open.';

    try {
        const result = await API.publishYouTube({
            filename: currentShareFile.filename,
            title,
            description: commonPostDescription(),
            privacy_status: youtubePrivacyStatus(),
        });
        const url = result.data.external_post_url;
        youtubePublishMessage.innerHTML = `Published to YouTube: <a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        showSuccess('Published to YouTube');
    } catch (err) {
        youtubePublishMessage.textContent = err.message;
        showError(err.message);
        publishYouTubeBtn.disabled = false;
    } finally {
        publishYouTubeBtn.textContent = 'Publish to YouTube';
    }
}

async function refreshShareFacebookStatus() {
    try {
        const result = await API.getFacebookStatus();
        const status = result.data || {};
        if (!status.configured) {
            shareFacebookStatus.textContent = 'Setup needed';
            shareFacebookStatus.className = 'status-pill status-inactive';
            facebookPublishMessage.textContent = 'Set Facebook app keys in .env, then connect Facebook in Company settings.';
            publishFacebookBtn.disabled = true;
            return;
        }
        if (!status.connected) {
            shareFacebookStatus.textContent = 'Not connected';
            shareFacebookStatus.className = 'status-pill status-inactive';
            facebookPublishMessage.textContent = 'Connect Facebook in Company settings first.';
            publishFacebookBtn.disabled = true;
            return;
        }

        shareFacebookStatus.textContent = 'Connected';
        shareFacebookStatus.className = 'status-pill status-active';
        facebookPublishMessage.textContent = status.external_account_name
            ? `Ready to publish to Page ${status.external_account_name}.`
            : 'Ready to publish to the connected Facebook Page.';
        publishFacebookBtn.disabled = false;
    } catch (err) {
        shareFacebookStatus.textContent = 'Error';
        shareFacebookStatus.className = 'status-pill status-inactive';
        facebookPublishMessage.textContent = err.message;
        publishFacebookBtn.disabled = true;
    }
}

async function publishCurrentFileToFacebook() {
    if (!currentShareFile?.filename) return;

    const title = commonPostTitle(255);
    if (!title) {
        showError('Facebook title is required');
        return;
    }

    publishFacebookBtn.disabled = true;
    publishFacebookBtn.textContent = 'Publishing...';
    facebookPublishMessage.textContent = 'Uploading MP4 to Facebook Page. Keep this page open.';

    try {
        const result = await API.publishFacebook({
            filename: currentShareFile.filename,
            title,
            description: commonPostDescription(),
        });
        const url = result.data.external_post_url;
        facebookPublishMessage.innerHTML = `Published to Facebook Page: <a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        showSuccess('Published to Facebook Page');
    } catch (err) {
        facebookPublishMessage.textContent = err.message;
        showError(err.message);
        publishFacebookBtn.disabled = false;
    } finally {
        publishFacebookBtn.textContent = 'Publish to Facebook Page';
    }
}

async function refreshShareInstagramStatus() {
    try {
        const result = await API.getInstagramStatus();
        const status = result.data || {};
        if (!status.facebook_connected) {
            shareInstagramStatus.textContent = 'Not connected';
            shareInstagramStatus.className = 'status-pill status-inactive';
            instagramPublishMessage.textContent = 'Connect a Facebook Page with a linked Instagram professional account first.';
            publishInstagramBtn.disabled = true;
            return;
        }
        if (!status.public_base_url_configured) {
            shareInstagramStatus.textContent = 'Setup needed';
            shareInstagramStatus.className = 'status-pill status-inactive';
            instagramPublishMessage.textContent = 'Set SOCIAL_PUBLIC_BASE_URL to a public app URL so Instagram can fetch the MP4.';
            publishInstagramBtn.disabled = true;
            return;
        }
        if (!status.connected) {
            shareInstagramStatus.textContent = 'No IG account';
            shareInstagramStatus.className = 'status-pill status-inactive';
            instagramPublishMessage.textContent = status.message || 'Link an Instagram professional account to the connected Facebook Page.';
            publishInstagramBtn.disabled = true;
            return;
        }

        shareInstagramStatus.textContent = 'Connected';
        shareInstagramStatus.className = 'status-pill status-active';
        instagramPublishMessage.textContent = status.external_account_name
            ? `Ready to publish to Instagram @${status.external_account_name}.`
            : 'Ready to publish to Instagram.';
        publishInstagramBtn.disabled = false;
    } catch (err) {
        shareInstagramStatus.textContent = 'Error';
        shareInstagramStatus.className = 'status-pill status-inactive';
        instagramPublishMessage.textContent = err.message;
        publishInstagramBtn.disabled = true;
    }
}

async function publishCurrentFileToInstagram() {
    if (!currentShareFile?.filename) return;

    const title = commonPostTitle(255);
    if (!title) {
        showError('Instagram title is required');
        return;
    }

    publishInstagramBtn.disabled = true;
    publishInstagramBtn.textContent = 'Publishing...';
    instagramPublishMessage.textContent = 'Publishing MP4 to Instagram. Keep this page open.';

    try {
        const result = await API.publishInstagram({
            filename: currentShareFile.filename,
            title,
            description: commonPostDescription(),
        });
        const url = result.data.external_post_url;
        instagramPublishMessage.innerHTML = `Published to Instagram: <a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        showSuccess('Published to Instagram');
    } catch (err) {
        instagramPublishMessage.textContent = err.message;
        showError(err.message);
        publishInstagramBtn.disabled = false;
    } finally {
        publishInstagramBtn.textContent = 'Publish to Instagram';
    }
}

async function refreshShareXStatus() {
    try {
        const result = await API.getXStatus();
        const status = result.data || {};
        if (!status.configured) {
            shareXStatus.textContent = 'Setup needed';
            shareXStatus.className = 'status-pill status-inactive';
            xPublishMessage.textContent = 'Set X app keys in .env, then connect X in Company settings.';
            publishXBtn.disabled = true;
            return;
        }
        if (!status.connected) {
            shareXStatus.textContent = 'Not connected';
            shareXStatus.className = 'status-pill status-inactive';
            xPublishMessage.textContent = 'Connect X in Company settings first.';
            publishXBtn.disabled = true;
            return;
        }

        shareXStatus.textContent = 'Connected';
        shareXStatus.className = 'status-pill status-active';
        xPublishMessage.textContent = status.external_account_name
            ? `Ready to publish to ${status.external_account_name}.`
            : 'Ready to publish to X.';
        publishXBtn.disabled = false;
    } catch (err) {
        shareXStatus.textContent = 'Error';
        shareXStatus.className = 'status-pill status-inactive';
        xPublishMessage.textContent = err.message;
        publishXBtn.disabled = true;
    }
}

async function publishCurrentFileToX() {
    if (!currentShareFile?.filename) return;

    const title = commonPostTitle(255);
    if (!title) {
        showError('X Post title is required');
        return;
    }

    publishXBtn.disabled = true;
    publishXBtn.textContent = 'Publishing...';
    xPublishMessage.textContent = 'Uploading MP4 and publishing to X. Keep this page open.';

    try {
        const result = await API.publishX({
            filename: currentShareFile.filename,
            title,
            description: commonPostDescription(),
        });
        const url = result.data.external_post_url;
        xPublishMessage.innerHTML = `Published to X: <a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        showSuccess('Published to X');
    } catch (err) {
        xPublishMessage.textContent = err.message;
        showError(err.message);
        publishXBtn.disabled = false;
    } finally {
        publishXBtn.textContent = 'Publish to X';
    }
}

async function refreshShareLinkedInStatus() {
    await refreshShareLinkedInTargetStatus({
        request: () => API.getLinkedInPageStatus(),
        statusEl: shareLinkedInStatus,
        messageEl: linkedinPublishMessage,
        publishBtn: publishLinkedInBtn,
        setupMessage: 'Set LinkedIn app keys in .env, then connect a LinkedIn Page in Company settings.',
        disconnectedMessage: 'Connect LinkedIn Page in Company settings first.',
        readyMessage: name => name
            ? `Ready to publish to Page ${name}.`
            : 'Ready to publish to the connected LinkedIn Page.',
    });
}

async function refreshShareLinkedInPersonalStatus() {
    await refreshShareLinkedInTargetStatus({
        request: () => API.getLinkedInPersonalStatus(),
        statusEl: shareLinkedInPersonalStatus,
        messageEl: linkedinPersonalPublishMessage,
        publishBtn: publishLinkedInPersonalBtn,
        setupMessage: 'Set LinkedIn app keys in .env, then connect a LinkedIn personal profile in Company settings.',
        disconnectedMessage: 'Connect LinkedIn personal profile in Company settings first.',
        readyMessage: name => name
            ? `Ready to publish to ${name}.`
            : 'Ready to publish to the connected LinkedIn profile.',
    });
}

async function refreshShareLinkedInTargetStatus(options) {
    try {
        const result = await options.request();
        const status = result.data || {};
        if (!status.configured) {
            options.statusEl.textContent = 'Setup needed';
            options.statusEl.className = 'status-pill status-inactive';
            options.messageEl.textContent = options.setupMessage;
            options.publishBtn.disabled = true;
            return;
        }
        if (!status.connected) {
            options.statusEl.textContent = 'Not connected';
            options.statusEl.className = 'status-pill status-inactive';
            options.messageEl.textContent = options.disconnectedMessage;
            options.publishBtn.disabled = true;
            return;
        }

        options.statusEl.textContent = 'Connected';
        options.statusEl.className = 'status-pill status-active';
        options.messageEl.textContent = options.readyMessage(status.external_account_name);
        options.publishBtn.disabled = false;
    } catch (err) {
        options.statusEl.textContent = 'Error';
        options.statusEl.className = 'status-pill status-inactive';
        options.messageEl.textContent = err.message;
        options.publishBtn.disabled = true;
    }
}

async function publishCurrentFileToLinkedIn() {
    await publishCurrentFileToLinkedInTarget({
        publishBtn: publishLinkedInBtn,
        messageEl: linkedinPublishMessage,
        request: payload => API.publishLinkedInPage(payload),
        titleRequiredMessage: 'LinkedIn Page title is required',
        uploadingMessage: 'Uploading MP4 to LinkedIn Page. Keep this page open.',
        publishedPrefix: 'Published to LinkedIn Page',
        successMessage: 'Published to LinkedIn Page',
        buttonText: 'Publish to LinkedIn Page',
    });
}

async function publishCurrentFileToLinkedInPersonal() {
    await publishCurrentFileToLinkedInTarget({
        publishBtn: publishLinkedInPersonalBtn,
        messageEl: linkedinPersonalPublishMessage,
        request: payload => API.publishLinkedInPersonal(payload),
        titleRequiredMessage: 'LinkedIn personal title is required',
        uploadingMessage: 'Uploading MP4 to LinkedIn profile. Keep this page open.',
        publishedPrefix: 'Published to LinkedIn profile',
        successMessage: 'Published to LinkedIn profile',
        buttonText: 'Publish to LinkedIn Profile',
    });
}

async function publishCurrentFileToLinkedInTarget(options) {
    if (!currentShareFile?.filename) return;

    const title = commonPostTitle(200);
    if (!title) {
        showError(options.titleRequiredMessage);
        return;
    }

    options.publishBtn.disabled = true;
    options.publishBtn.textContent = 'Publishing...';
    options.messageEl.textContent = options.uploadingMessage;

    try {
        const result = await options.request({
            filename: currentShareFile.filename,
            title,
            description: commonPostDescription(),
            visibility: linkedInVisibility(),
        });
        const url = result.data.external_post_url;
        options.messageEl.innerHTML = `${options.publishedPrefix}: <a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        showSuccess(options.successMessage);
    } catch (err) {
        options.messageEl.textContent = err.message;
        showError(err.message);
        options.publishBtn.disabled = false;
    } finally {
        options.publishBtn.textContent = options.buttonText;
    }
}

async function copyText(text, message) {
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
