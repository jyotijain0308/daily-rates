let countries = [];

const countriesBody = document.getElementById('countriesBody');
const countryModal = document.getElementById('countryModal');
const countryForm = document.getElementById('countryForm');
const countryModalTitle = document.getElementById('countryModalTitle');
const countryId = document.getElementById('countryId');
const countryName = document.getElementById('countryName');
const countryCurrencyCode = document.getElementById('countryCurrencyCode');
const countryIsActive = document.getElementById('countryIsActive');
const countryFlagInput = document.getElementById('countryFlagInput');
const browseCountryFlagBtn = document.getElementById('browseCountryFlagBtn');
const countryFlagFileName = document.getElementById('countryFlagFileName');
const countryFlagPreviewImg = document.getElementById('countryFlagPreviewImg');
const countryFlagPreviewEmpty = document.getElementById('countryFlagPreviewEmpty');
let selectedCountryFlagFile = null;
let selectedCountryFlagPreviewUrl = null;

document.getElementById('addCountryBtn').addEventListener('click', () => openCountryModal());
document.getElementById('closeCountryModalBtn').addEventListener('click', closeCountryModal);
document.getElementById('cancelCountryModalBtn').addEventListener('click', closeCountryModal);
countryFlagInput.addEventListener('change', handleCountryFlagSelected);
browseCountryFlagBtn.addEventListener('click', () => countryFlagInput.click());
countryForm.addEventListener('submit', saveCountry);
countryModal.addEventListener('click', (e) => {
    if (e.target === countryModal) closeCountryModal();
});

loadCountries();

async function loadCountries() {
    try {
        const result = await API.getManagedCountries();
        countries = Array.isArray(result.data) ? result.data : [];
        renderCountries();
    } catch (err) {
        countriesBody.innerHTML = `<tr><td colspan="5" class="empty-state">${escapeHtml(err.message)}</td></tr>`;
        showError(err.message);
    }
}

function renderCountries() {
    if (!countries.length) {
        countriesBody.innerHTML = '<tr><td colspan="5" class="empty-state">No countries configured.</td></tr>';
        return;
    }

    countriesBody.innerHTML = countries.map(country => `
        <tr>
            <td>${escapeHtml(country.name)}</td>
            <td>${escapeHtml(country.currency_code || '—')}</td>
            <td>${renderCountryLogo(country)}</td>
            <td><span class="${country.is_active ? 'status-pill status-active' : 'status-pill status-inactive'}">${country.is_active ? 'Active' : 'Inactive'}</span></td>
            <td>
                <button type="button" class="btn btn-sm btn-secondary edit-country-btn" data-id="${country.id}">Edit</button>
                <button type="button" class="btn btn-sm btn-danger delete-country-btn" data-id="${country.id}">Delete</button>
            </td>
        </tr>
    `).join('');

    countriesBody.querySelectorAll('.edit-country-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const country = countries.find(item => item.id === parseInt(btn.dataset.id, 10));
            if (country) openCountryModal(country);
        });
    });

    countriesBody.querySelectorAll('.delete-country-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteCountry(parseInt(btn.dataset.id, 10)));
    });

    countriesBody.querySelectorAll('.country-logo-img').forEach(img => {
        img.addEventListener('error', () => {
            const cell = img.closest('.country-logo-cell');
            if (cell) {
                cell.innerHTML = '<span class="product-thumb product-thumb-empty">No image</span>';
            }
        });
    });
}

function renderCountryLogo(country) {
    if (!country.logo_url) {
        return `
            <div class="country-logo-cell">
                <span class="product-thumb product-thumb-empty">No image</span>
            </div>
        `;
    }

    return `
        <div class="country-logo-cell">
            <img class="country-logo-img" src="${escapeHtml(country.logo_url)}" alt="${escapeHtml(country.name)} logo">
        </div>
    `;
}

function openCountryModal(country = null) {
    countryModalTitle.textContent = country ? 'Edit Country' : 'Add Country';
    countryId.value = country?.id || '';
    countryName.value = country?.name || '';
    countryCurrencyCode.value = country?.currency_code || '';
    countryIsActive.checked = country ? Boolean(country.is_active) : true;
    resetCountryFlagSelection();
    setCountryFlagPreview(country?.logo_url || '');
    countryModal.style.display = 'flex';
    countryName.focus();
}

function closeCountryModal() {
    countryModal.style.display = 'none';
    countryForm.reset();
    countryId.value = '';
    resetCountryFlagSelection();
}

function handleCountryFlagSelected(e) {
    const file = e.target.files[0];
    if (!file) {
        resetCountryFlagSelection();
        return;
    }

    if (!file.type.startsWith('image/')) {
        resetCountryFlagSelection();
        showError('Please select an image file');
        return;
    }

    selectedCountryFlagFile = file;
    countryFlagFileName.textContent = file.name;
    if (selectedCountryFlagPreviewUrl) {
        URL.revokeObjectURL(selectedCountryFlagPreviewUrl);
    }
    selectedCountryFlagPreviewUrl = URL.createObjectURL(file);
    setCountryFlagPreview(selectedCountryFlagPreviewUrl);
}

function resetCountryFlagSelection() {
    selectedCountryFlagFile = null;
    countryFlagInput.value = '';
    countryFlagFileName.textContent = 'No file selected';
    if (selectedCountryFlagPreviewUrl) {
        URL.revokeObjectURL(selectedCountryFlagPreviewUrl);
        selectedCountryFlagPreviewUrl = null;
    }
    setCountryFlagPreview('');
}

function setCountryFlagPreview(src) {
    if (src) {
        countryFlagPreviewImg.src = src;
        countryFlagPreviewImg.style.display = 'inline-flex';
        countryFlagPreviewEmpty.style.display = 'none';
    } else {
        countryFlagPreviewImg.src = '';
        countryFlagPreviewImg.style.display = 'none';
        countryFlagPreviewEmpty.style.display = 'inline-flex';
    }
}

async function saveCountry(e) {
    e.preventDefault();

    const payload = {
        name: countryName.value.trim(),
        currency_code: countryCurrencyCode.value.trim().toUpperCase(),
        is_active: countryIsActive.checked,
    };

    try {
        let result;
        if (countryId.value) {
            result = await API.updateCountry(countryId.value, payload);
            showSuccess('Country updated');
        } else {
            result = await API.createCountry(payload);
            showSuccess('Country created');
        }

        if (selectedCountryFlagFile && result?.data?.id) {
            await API.uploadCountryFlag(result.data.id, selectedCountryFlagFile);
            showSuccess('Country flag uploaded');
        }

        closeCountryModal();
        await loadCountries();
    } catch (err) {
        showError(err.message);
    }
}

async function deleteCountry(id) {
    const country = countries.find(item => item.id === id);
    if (!country) return;
    if (!confirm(`Delete ${country.name}?`)) return;

    try {
        await API.deleteCountry(id);
        showSuccess('Country deleted');
        await loadCountries();
    } catch (err) {
        showError(err.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
