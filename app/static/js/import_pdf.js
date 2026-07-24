let extractedCsvContent = null;

const pdfUploadZone = document.getElementById('pdfUploadZone');
const pdfFileInput = document.getElementById('pdfFileInput');
const selectedPdfInfo = document.getElementById('selectedPdfInfo');
const pdfPreviewSection = document.getElementById('pdfPreviewSection');
const pdfPreviewTable = document.querySelector('#pdfPreviewTable tbody');
const pdfValidCountBadge = document.getElementById('pdfValidCountBadge');
const pdfErrorCountBadge = document.getElementById('pdfErrorCountBadge');
const pdfErrorList = document.getElementById('pdfErrorList');
const cancelPdfImportBtn = document.getElementById('cancelPdfImportBtn');
const downloadExtractedCsvBtn = document.getElementById('downloadExtractedCsvBtn');
const savePdfImportBtn = document.getElementById('savePdfImportBtn');

registerPdfUploadZone();
cancelPdfImportBtn.addEventListener('click', resetPdfImport);
downloadExtractedCsvBtn.addEventListener('click', downloadExtractedCsv);
savePdfImportBtn.addEventListener('click', savePdfToDatabase);

pdfFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handlePdfFile(file);
});

function registerPdfUploadZone() {
    pdfUploadZone.addEventListener('click', () => pdfFileInput.click());

    pdfUploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        pdfUploadZone.classList.add('dragover');
    });

    pdfUploadZone.addEventListener('dragleave', () => {
        pdfUploadZone.classList.remove('dragover');
    });

    pdfUploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        pdfUploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handlePdfFile(file);
    });
}

async function handlePdfFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showError('Please select a PDF file');
        return;
    }

    selectedPdfInfo.style.display = 'block';
    selectedPdfInfo.textContent = `Selected PDF: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;

    try {
        savePdfImportBtn.disabled = true;
        downloadExtractedCsvBtn.disabled = true;
        savePdfImportBtn.textContent = 'Reading PDF...';

        const result = await API.previewPdfImport(file);
        extractedCsvContent = result.content;
        showPdfPreview(result.preview);
        downloadExtractedCsvBtn.disabled = !extractedCsvContent;
        showInfo(`PDF converted to CSV with ${result.extracted_count} extracted row${result.extracted_count !== 1 ? 's' : ''}`);
    } catch (err) {
        showError(err.message);
        resetPdfPreview();
    } finally {
        savePdfImportBtn.textContent = 'Save to Database';
    }
}

function showPdfPreview(preview) {
    pdfPreviewSection.style.display = 'block';
    pdfPreviewTable.innerHTML = '';

    const { valid_count, error_count, sample_data, errors } = preview;
    pdfValidCountBadge.textContent = `${valid_count} valid row${valid_count !== 1 ? 's' : ''}`;

    if (error_count > 0) {
        pdfErrorCountBadge.style.display = 'inline-block';
        pdfErrorCountBadge.textContent = `${error_count} issue${error_count !== 1 ? 's' : ''}`;
        pdfErrorList.style.display = 'block';
        pdfErrorList.innerHTML = `<ul>${errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul>`;
    } else {
        pdfErrorCountBadge.style.display = 'none';
        pdfErrorList.style.display = 'none';
    }

    if (sample_data.length === 0) {
        pdfPreviewTable.innerHTML = '<tr><td colspan="6" class="empty-state">No valid rows found</td></tr>';
        savePdfImportBtn.disabled = true;
        return;
    }

    sample_data.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${escapeHtml(row.product_name)}</td>
            <td>${escapeHtml(row.country_of_origin)}</td>
            <td>${escapeHtml(row.shipment_by)}</td>
            <td>${escapeHtml(row.weight_kg)}</td>
            <td>${escapeHtml(row.packing)}</td>
            <td>AED ${formatRate(row.price_aed)}</td>
        `;
        pdfPreviewTable.appendChild(tr);
    });

    if (valid_count > 5) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td colspan="6" class="text-muted" style="text-align:center;">... and ${valid_count - 5} more row${valid_count - 5 !== 1 ? 's' : ''}</td>`;
        pdfPreviewTable.appendChild(tr);
    }

    savePdfImportBtn.disabled = valid_count === 0;
}

function downloadExtractedCsv() {
    if (!extractedCsvContent) {
        showError('No extracted CSV to download');
        return;
    }

    const blob = new Blob([extractedCsvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'products_from_pdf.csv';
    a.click();
    URL.revokeObjectURL(url);
}

async function savePdfToDatabase() {
    if (!extractedCsvContent) {
        showError('No extracted CSV to save');
        return;
    }

    savePdfImportBtn.disabled = true;
    savePdfImportBtn.textContent = 'Saving...';

    try {
        const result = await API.saveImport(extractedCsvContent);
        showSuccess(result.message);
        if (result.data.errors?.length) {
            showWarning(`${result.data.errors.length} row(s) had issues`);
        }
        resetPdfImport();
    } catch (err) {
        showError(err.message);
        savePdfImportBtn.disabled = false;
    } finally {
        savePdfImportBtn.textContent = 'Save to Database';
    }
}

function resetPdfPreview() {
    pdfPreviewSection.style.display = 'none';
    pdfPreviewTable.innerHTML = '';
    savePdfImportBtn.disabled = true;
    downloadExtractedCsvBtn.disabled = true;
}

function resetPdfImport() {
    extractedCsvContent = null;
    pdfFileInput.value = '';
    selectedPdfInfo.style.display = 'none';
    resetPdfPreview();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
