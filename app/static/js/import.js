let csvContent = null;
let selectedFile = null;

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('csvFileInput');
const previewSection = document.getElementById('previewSection');
const previewTable = document.querySelector('#previewTable tbody');
const saveBtn = document.getElementById('saveImportBtn');
const validCountBadge = document.getElementById('validCountBadge');
const errorCountBadge = document.getElementById('errorCountBadge');
const errorList = document.getElementById('errorList');
const selectedFileInfo = document.getElementById('selectedFileInfo');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
});

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

async function handleFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
        showError('Please select a CSV file');
        return;
    }

    selectedFile = file;
    selectedFileInfo.style.display = 'block';
    selectedFileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

    try {
        csvContent = await file.text();
        const result = await API.previewImport(file);
        showPreview(result.preview);
        showInfo('Preview ready — review and save when ready');
    } catch (err) {
        showError(err.message);
        resetPreview();
    }
}

function showPreview(preview) {
    previewSection.style.display = 'block';
    previewTable.innerHTML = '';

    const { valid_count, error_count, sample_data, errors } = preview;

    validCountBadge.textContent = `${valid_count} valid row${valid_count !== 1 ? 's' : ''}`;

    if (error_count > 0) {
        errorCountBadge.style.display = 'inline-block';
        errorCountBadge.textContent = `${error_count} error${error_count !== 1 ? 's' : ''}`;
        errorList.style.display = 'block';
        errorList.innerHTML = `<ul>${errors.map(e => `<li>${e}</li>`).join('')}</ul>`;
    } else {
        errorCountBadge.style.display = 'none';
        errorList.style.display = 'none';
    }

    if (sample_data.length === 0) {
        previewTable.innerHTML = '<tr><td colspan="6" class="empty-state">No valid rows found</td></tr>';
        saveBtn.disabled = true;
        return;
    }

    sample_data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${escapeHtml(row.product_name)}</td>
            <td>${escapeHtml(row.country_of_origin)}</td>
            <td>${escapeHtml(row.shipment_by)}</td>
            <td>${Number(row.weight_kg).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
            <td>${escapeHtml(row.packing)}</td>
            <td>AED ${formatRate(row.price_aed)}</td>
        `;
        previewTable.appendChild(tr);
    });

    if (valid_count > 5) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="6" class="text-muted" style="text-align:center;">... and ${valid_count - 5} more row${valid_count - 5 !== 1 ? 's' : ''}</td>`;
        previewTable.appendChild(tr);
    }

    saveBtn.disabled = valid_count === 0;
}

async function saveToDatabase() {
    if (!csvContent) {
        showError('No CSV content to save');
        return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        const result = await API.saveImport(csvContent);
        showSuccess(result.message);
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
    previewSection.style.display = 'none';
    previewTable.innerHTML = '';
    saveBtn.disabled = true;
}

function resetImport() {
    csvContent = null;
    selectedFile = null;
    fileInput.value = '';
    selectedFileInfo.style.display = 'none';
    resetPreview();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
