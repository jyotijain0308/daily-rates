let csvContent = null;
let selectedFile = null;

const csvUploadZone = document.getElementById('csvUploadZone');
// Image import is intentionally disabled. CSV import remains active.
// const imageUploadZone = document.getElementById('imageUploadZone');
const csvFileInput = document.getElementById('csvFileInput');
// const imageFileInput = document.getElementById('imageFileInput');
const previewSection = document.getElementById('previewSection');
const previewTable = document.querySelector('#previewTable tbody');
const saveBtn = document.getElementById('saveImportBtn');
const validCountBadge = document.getElementById('validCountBadge');
const createdCountBadge = document.getElementById('createdCountBadge');
const updatedCountBadge = document.getElementById('updatedCountBadge');
const skippedCountBadge = document.getElementById('skippedCountBadge');
const largeChangeCountBadge = document.getElementById('largeChangeCountBadge');
const errorCountBadge = document.getElementById('errorCountBadge');
const errorList = document.getElementById('errorList');
const selectedFileInfo = document.getElementById('selectedFileInfo');
let latestPreview = null;

registerUploadZone(csvUploadZone, csvFileInput, handleCsvFile);
// registerUploadZone(imageUploadZone, imageFileInput, handleImageFile);

csvFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleCsvFile(file);
});

// imageFileInput.addEventListener('change', (e) => {
//     const file = e.target.files[0];
//     if (file) handleImageFile(file);
// });

document.getElementById('downloadTemplateBtn').addEventListener('click', async () => {
    try {
        const result = await API.getTemplate();
        const blob = new Blob([result.template], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'products_template.csv';
        a.click();
        URL.revokeObjectURL(url);
        showSuccess('Blank template downloaded');
    } catch (err) {
        showError(err.message);
    }
});

document.getElementById('downloadSampleBtn')?.addEventListener('click', () => {
    showSuccess('Sample CSV download started');
});

document.getElementById('cancelImportBtn').addEventListener('click', resetImport);
saveBtn.addEventListener('click', saveToDatabase);

function registerUploadZone(zone, input, handler) {
    zone.addEventListener('click', () => input.click());

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handler(file);
    });
}

async function handleCsvFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showError('Please select a CSV file');
        return;
    }

    selectedFile = file;
    selectedFileInfo.style.display = 'block';
    selectedFileInfo.textContent = `Selected CSV: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

    try {
        csvContent = await file.text();
        const result = await API.previewImport(file);
        csvContent = result.content || csvContent;
        showPreview(result.preview);
        showInfo('Preview ready — review and save when ready');
    } catch (err) {
        showError(err.message);
        resetPreview();
    }
}

// async function handleImageFile(file) {
//     const allowedExtensions = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'];
//     const lowerName = file.name.toLowerCase();
//     if (!allowedExtensions.some(ext => lowerName.endsWith(ext))) {
//         showError('Please select a PNG, JPG, JPEG, WEBP, BMP, or TIFF image');
//         return;
//     }
//
//     selectedFile = file;
//     selectedFileInfo.style.display = 'block';
//     selectedFileInfo.textContent = `Selected image: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
//
//     try {
//         saveBtn.disabled = true;
//         saveBtn.textContent = 'Reading image...';
//         const result = await API.previewImageImport(file);
//         csvContent = result.content;
//         showPreview(result.preview);
//         showInfo('Image table extracted — review OCR results before saving');
//     } catch (err) {
//         showError(err.message);
//         resetPreview();
//     } finally {
//         saveBtn.textContent = 'Save to Database';
//     }
// }

function showPreview(preview) {
    latestPreview = preview;
    previewSection.style.display = 'block';
    previewTable.innerHTML = '';

    const {
        valid_count,
        error_count,
        sample_data,
        errors,
        created_count = 0,
        updated_count = 0,
        skipped_count = 0,
        large_change_count = 0,
    } = preview;
    const actionableCount = created_count + updated_count;

    validCountBadge.textContent = `${valid_count} valid row${valid_count !== 1 ? 's' : ''}`;
    createdCountBadge.textContent = `${created_count} created`;
    updatedCountBadge.textContent = `${updated_count} updated`;
    skippedCountBadge.textContent = `${skipped_count} skipped`;

    if (large_change_count > 0) {
        largeChangeCountBadge.style.display = 'inline-block';
        largeChangeCountBadge.textContent = `${large_change_count} large change${large_change_count !== 1 ? 's' : ''}`;
    } else {
        largeChangeCountBadge.style.display = 'none';
    }

    if (error_count > 0) {
        errorCountBadge.style.display = 'inline-block';
        errorCountBadge.textContent = `${error_count} error${error_count !== 1 ? 's' : ''}`;
        errorList.style.display = 'block';
        errorList.innerHTML = `<ul>${errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul>`;
    } else {
        errorCountBadge.style.display = 'none';
        errorList.style.display = 'none';
    }

    if (sample_data.length === 0) {
        previewTable.innerHTML = '<tr><td colspan="10" class="empty-state">No rows to create or update</td></tr>';
        saveBtn.disabled = true;
        return;
    }

    sample_data.forEach(row => {
        const tr = document.createElement('tr');
        if (row.large_change) tr.classList.add('large-change-row');
        const change = formatImportChange(row);
        tr.innerHTML = `
            <td><span class="badge ${actionBadgeClass(row.action)}">${escapeHtml(row.action)}</span></td>
            <td>${escapeHtml(row.product_name)}</td>
            <td>${escapeHtml(row.country_of_origin)}</td>
            <td>${escapeHtml(row.shipment_by)}</td>
            <td>${escapeHtml(row.weight_kg)}</td>
            <td>${escapeHtml(row.packing)}</td>
            <td>${row.old_price_aed === null || row.old_price_aed === undefined ? '—' : `AED ${formatRate(row.old_price_aed)}`}</td>
            <td>AED ${formatRate(row.new_price_aed ?? row.price_aed)}</td>
            <td class="${change.className}">${change.text}</td>
            <td>${escapeHtml(row.reason || '')}</td>
        `;
        previewTable.appendChild(tr);
    });

    saveBtn.disabled = valid_count === 0 || actionableCount === 0;
}

async function saveToDatabase() {
    if (!csvContent) {
        showError('No CSV content to save');
        return;
    }

    const created = latestPreview?.created_count || 0;
    const updated = latestPreview?.updated_count || 0;
    const skipped = latestPreview?.skipped_count || 0;
    const large = latestPreview?.large_change_count || 0;
    const message = `Apply this import?\n\nCreate: ${created}\nUpdate: ${updated}\nSkip: ${skipped}\nLarge rate changes: ${large}`;
    if (!confirm(message)) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const result = await API.saveImport(csvContent);
        const data = result.data || {};
        showSuccess(result.message);
        if (data.large_change_count) {
            showWarning(`${data.large_change_count} large rate change(s) applied`);
        }
        if (result.data.errors?.length) {
            showWarning(`${result.data.errors.length} row(s) had issues`);
        }
        resetImport();
    } catch (err) {
        showError(err.message);
        saveBtn.disabled = false;
    } finally {
        saveBtn.textContent = 'Save to Database';
    }
}

function resetPreview() {
    latestPreview = null;
    previewSection.style.display = 'none';
    previewTable.innerHTML = '';
    saveBtn.disabled = true;
}

function resetImport() {
    csvContent = null;
    selectedFile = null;
    csvFileInput.value = '';
    // imageFileInput.value = '';
    selectedFileInfo.style.display = 'none';
    resetPreview();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

function actionBadgeClass(action) {
    if (action === 'created') return 'badge-success';
    if (action === 'updated') return 'badge-warning';
    return '';
}

function formatImportChange(row) {
    if (row.change_percent === null || row.change_percent === undefined) {
        if (row.action === 'created') return { text: 'New', className: 'rate-neutral' };
        return { text: '—', className: 'rate-neutral' };
    }

    const sign = row.change_percent > 0 ? '+' : '';
    const className = row.large_change
        ? 'rate-large'
        : row.change_percent > 0
            ? 'rate-up'
            : row.change_percent < 0
                ? 'rate-down'
                : 'rate-neutral';
    const marker = row.large_change ? ' large' : '';
    return {
        text: `${sign}${Number(row.change_percent).toFixed(2)}%${marker}`,
        className,
    };
}
