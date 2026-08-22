let products = [];

const productsBody = document.getElementById('productsBody');
const productSearch = document.getElementById('productSearch');
const productCount = document.getElementById('productCount');
const productModal = document.getElementById('productModal');
const productForm = document.getElementById('productForm');
const imagePreviewModal = document.getElementById('imagePreviewModal');
const imagePreviewImg = document.getElementById('imagePreviewImg');
const imagePreviewTitle = document.getElementById('imagePreviewTitle');
const imagePreviewEmpty = document.getElementById('imagePreviewEmpty');
const productImageInput = document.getElementById('productImageInput');
const replaceImageBtn = document.getElementById('replaceImageBtn');
const fetchPexelsImageBtn = document.getElementById('fetchPexelsImageBtn');
const pexelsImageDescription = document.getElementById('pexelsImageDescription');
const pexelsImageOptions = document.getElementById('pexelsImageOptions');
let selectedImageProductId = null;
let pexelsSearchPage = 1;
let currentPexelsCandidates = [];
let lastPexelsDescription = '';
let showMissingImagesOnly = new URLSearchParams(window.location.search).get('missing_images') === '1';

document.getElementById('addProductBtn').addEventListener('click', () => openModal());
document.getElementById('closeModalBtn').addEventListener('click', closeModal);
document.getElementById('cancelModalBtn').addEventListener('click', closeModal);
document.getElementById('closeImagePreviewBtn').addEventListener('click', closeImagePreview);
replaceImageBtn.addEventListener('click', () => {
    if (selectedImageProductId) openImageUpload(selectedImageProductId);
});
fetchPexelsImageBtn.addEventListener('click', fetchProductImageFromPexels);
productImageInput.addEventListener('change', handleProductImageSelected);
productForm.addEventListener('submit', handleFormSubmit);
productSearch.addEventListener('input', renderProducts);

productModal.addEventListener('click', (e) => {
    if (e.target === productModal) closeModal();
});

imagePreviewModal.addEventListener('click', (e) => {
    if (e.target === imagePreviewModal) closeImagePreview();
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && imagePreviewModal.style.display !== 'none') {
        closeImagePreview();
    }
});

loadProducts();
loadCountries();

async function loadCountries() {
    try {
        const result = await API.getCountries();
        const options = document.getElementById('countryOptions');
        options.innerHTML = result.data.map(country => `<option value="${escapeHtml(country)}"></option>`).join('');
    } catch (err) {
        console.warn('Could not load countries', err);
    }
}

async function loadProducts() {
    try {
        const result = await API.getProducts(1, 200);
        products = result.data;
        if (showMissingImagesOnly) {
            productSearch.value = '';
        }
        productCount.textContent = `${result.pagination.total} product${result.pagination.total !== 1 ? 's' : ''}`;
        renderProducts();
    } catch (err) {
        productsBody.innerHTML = `<tr><td colspan="9" class="empty-state">${err.message}</td></tr>`;
        showError(err.message);
    }
}

function renderProducts() {
    const query = productSearch.value.toLowerCase().trim();
    const filtered = products.filter(p => {
        if (showMissingImagesOnly && p.has_image) {
            return false;
        }
        return (
            p.product_name.toLowerCase().includes(query) ||
            p.country_of_origin.toLowerCase().includes(query) ||
            p.shipment_by.toLowerCase().includes(query)
        );
    });

    if (showMissingImagesOnly) {
        productCount.innerHTML = `
            ${filtered.length} product${filtered.length !== 1 ? 's' : ''} without images
            <a href="${API.url('/products')}" class="inline-link">Clear filter</a>
        `;
    } else {
        productCount.textContent = `${filtered.length} product${filtered.length !== 1 ? 's' : ''}`;
    }

    if (filtered.length === 0) {
        productsBody.innerHTML = `<tr><td colspan="9" class="empty-state">${
            showMissingImagesOnly
                ? 'No products without images found.'
                : 'No products found. Import CSV or add a product.'
        }</td></tr>`;
        return;
    }

    productsBody.innerHTML = filtered.map(p => {
        const imageCell = p.image_url
            ? `<button type="button" class="product-thumb-btn" data-id="${p.id}" aria-label="View ${escapeHtml(p.product_name)} image"><img class="product-thumb" src="${escapeHtml(p.image_url)}" alt="${escapeHtml(p.product_name)}"></button>`
            : '<span class="product-thumb product-thumb-empty">No image</span>';

        return `
            <tr data-id="${p.id}">
                <td>${imageCell}</td>
                <td class="editable" data-field="product_name">${escapeHtml(p.product_name)}</td>
                <td class="editable" data-field="country_of_origin">${escapeHtml(p.country_of_origin)}</td>
                <td class="editable" data-field="shipment_by">${escapeHtml(p.shipment_by)}</td>
                <td class="editable" data-field="weight_kg">${escapeHtml(p.weight_kg)}</td>
                <td class="editable" data-field="packing">${escapeHtml(p.packing)}</td>
                <td class="editable" data-field="price_aed">AED ${formatRate(p.price_aed)}</td>
                <td class="text-muted">${formatDate(p.updated_at)}</td>
                <td>
                    <button class="btn btn-sm btn-secondary image-btn" data-id="${p.id}">Image</button>
                    <button class="btn btn-sm btn-secondary edit-btn" data-id="${p.id}">Edit</button>
                    <button class="btn btn-sm btn-danger delete-btn" data-id="${p.id}">Delete</button>
                </td>
            </tr>
        `;
    }).join('');

    productsBody.querySelectorAll('.editable').forEach(cell => {
        cell.addEventListener('dblclick', () => startInlineEdit(cell));
    });

    productsBody.querySelectorAll('.product-thumb-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const product = products.find(p => p.id === parseInt(btn.dataset.id));
            if (product) openImagePreview(product);
        });
    });

    productsBody.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const product = products.find(p => p.id === parseInt(btn.dataset.id));
            if (product) openModal(product);
        });
    });

    productsBody.querySelectorAll('.image-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const product = products.find(p => p.id === parseInt(btn.dataset.id));
            if (product) openImagePreview(product);
        });
    });

    productsBody.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteProduct(parseInt(btn.dataset.id)));
    });
}

function openImagePreview(product) {
    selectedImageProductId = product.id;
    resetPexelsOptions();
    imagePreviewTitle.textContent = product.product_name;
    if (pexelsImageDescription) {
        pexelsImageDescription.value = [product.product_name, product.country_of_origin]
            .filter(Boolean)
            .join(' ');
    }
    if (product.image_url) {
        imagePreviewImg.style.display = 'block';
        imagePreviewEmpty.style.display = 'none';
        imagePreviewImg.src = product.image_url;
        imagePreviewImg.alt = product.product_name;
    } else {
        imagePreviewImg.style.display = 'none';
        imagePreviewEmpty.style.display = 'flex';
        imagePreviewImg.src = '';
        imagePreviewImg.alt = '';
    }
    imagePreviewModal.style.display = 'flex';
}

function closeImagePreview() {
    imagePreviewModal.style.display = 'none';
    imagePreviewImg.src = '';
    imagePreviewImg.alt = '';
    imagePreviewEmpty.style.display = 'none';
    resetPexelsOptions();
    selectedImageProductId = null;
}

function resetPexelsOptions() {
    pexelsSearchPage = 1;
    currentPexelsCandidates = [];
    lastPexelsDescription = '';
    if (pexelsImageOptions) {
        pexelsImageOptions.innerHTML = '';
        pexelsImageOptions.style.display = 'none';
    }
    if (fetchPexelsImageBtn) {
        fetchPexelsImageBtn.textContent = 'Fetch from Pexels';
    }
}

function openImageUpload(productId) {
    selectedImageProductId = productId;
    productImageInput.value = '';
    productImageInput.click();
}

async function handleProductImageSelected(e) {
    const file = e.target.files[0];
    if (!file || !selectedImageProductId) return;

    if (!file.type.startsWith('image/')) {
        showError('Please select an image file');
        return;
    }

    try {
        const result = await API.updateProductImage(selectedImageProductId, file);
        const idx = products.findIndex(p => p.id === selectedImageProductId);
        if (idx >= 0) products[idx] = result.data;

        renderProducts();
        if (imagePreviewModal.style.display !== 'none') {
            openImagePreview(result.data);
        }
        showSuccess('Product image updated');
    } catch (err) {
        showError(err.message);
    }
}

async function fetchProductImageFromPexels() {
    if (!selectedImageProductId) return;

    fetchPexelsImageBtn.disabled = true;
    fetchPexelsImageBtn.textContent = 'Fetching...';

    try {
        const description = pexelsImageDescription?.value || '';
        if (description !== lastPexelsDescription) {
            pexelsSearchPage = 1;
        }

        const result = await API.searchProductImagesFromPexels(selectedImageProductId, {
            description,
            page: pexelsSearchPage,
        });
        currentPexelsCandidates = result.data || [];
        renderPexelsOptions(currentPexelsCandidates);
        lastPexelsDescription = description;
        pexelsSearchPage += 1;
        showSuccess('Select one of the Pexels images');
    } catch (err) {
        showError(err.message);
    } finally {
        fetchPexelsImageBtn.disabled = false;
        fetchPexelsImageBtn.textContent = pexelsSearchPage > 1 ? 'Fetch different' : 'Fetch from Pexels';
    }
}

function renderPexelsOptions(candidates) {
    if (!pexelsImageOptions) return;

    if (!candidates.length) {
        pexelsImageOptions.innerHTML = '';
        pexelsImageOptions.style.display = 'none';
        return;
    }

    pexelsImageOptions.innerHTML = candidates.map((candidate, index) => `
        <div class="pexels-image-option">
            <img src="${escapeHtml(candidate.thumb_url || candidate.image_url)}" alt="${escapeHtml(candidate.alt || 'Pexels product image')}">
            <div class="pexels-image-credit">${candidate.photographer ? `Photo: ${escapeHtml(candidate.photographer)}` : ''}</div>
            <button type="button" class="btn btn-sm btn-primary pexels-select-btn" data-index="${index}">Use this image</button>
        </div>
    `).join('');
    pexelsImageOptions.style.display = 'grid';

    pexelsImageOptions.querySelectorAll('.pexels-select-btn').forEach(btn => {
        btn.addEventListener('click', () => selectPexelsImage(parseInt(btn.dataset.index, 10), btn));
    });
}

async function selectPexelsImage(index, button) {
    const candidate = currentPexelsCandidates[index];
    if (!candidate || !selectedImageProductId) return;

    button.disabled = true;
    button.textContent = 'Saving...';

    try {
        const result = await API.selectProductImageFromPexels(selectedImageProductId, candidate.image_url);
        const idx = products.findIndex(p => p.id === selectedImageProductId);
        if (idx >= 0) products[idx] = result.data;

        renderProducts();
        openImagePreview(result.data);
        showSuccess('Product image updated from Pexels');
    } catch (err) {
        showError(err.message);
        button.disabled = false;
        button.textContent = 'Use this image';
    }
}

function startInlineEdit(cell) {
    const row = cell.closest('tr');
    const id = parseInt(row.dataset.id);
    const field = cell.dataset.field;
    const product = products.find(p => p.id === id);
    if (!product) return;

    const currentValue = product[field] ?? '';
    const input = document.createElement('input');
    input.className = 'inline-input';
    input.value = currentValue;
    input.type = ['serial_no', 'price_aed'].includes(field) ? 'number' : 'text';
    if (field === 'price_aed') input.step = '0.01';
    if (field === 'serial_no') input.step = '1';

    cell.textContent = '';
    cell.appendChild(input);
    input.focus();
    input.select();

    const save = async () => {
        const newValue = input.value.trim();
        const payload = {
            [field]: field === 'price_aed'
                ? parseFloat(newValue)
                : field === 'serial_no'
                    ? (newValue ? parseInt(newValue, 10) : null)
                    : newValue
        };

        try {
            const result = await API.updateProduct(id, payload);
            const idx = products.findIndex(p => p.id === id);
            if (idx >= 0) products[idx] = result.data;
            renderProducts();
            showSuccess(`Updated ${field.replace('_', ' ')}`);
        } catch (err) {
            showError(err.message);
            renderProducts();
        }
    };

    input.addEventListener('blur', save);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') input.blur();
        if (e.key === 'Escape') renderProducts();
    });
}

function openModal(product = null) {
    document.getElementById('modalTitle').textContent = product ? 'Edit Product' : 'Add Product';
    document.getElementById('productId').value = product?.id || '';
    document.getElementById('productSerialNo').value = product?.serial_no ?? '';
    document.getElementById('productCountryOfOrigin').value = product?.country_of_origin || 'India';
    document.getElementById('productShipmentBy').value = product?.shipment_by || '';
    document.getElementById('productName').value = product?.product_name || '';
    document.getElementById('productWeightKg').value = product?.weight_kg ?? '';
    document.getElementById('productPacking').value = product?.packing || '';
    document.getElementById('productPriceAed').value = product?.price_aed ?? '';
    productModal.style.display = 'flex';
}

function closeModal() {
    productModal.style.display = 'none';
    productForm.reset();
}

async function handleFormSubmit(e) {
    e.preventDefault();

    const id = document.getElementById('productId').value;
    const payload = {
        serial_no: document.getElementById('productSerialNo').value
            ? parseInt(document.getElementById('productSerialNo').value, 10) : null,
        country_of_origin: document.getElementById('productCountryOfOrigin').value.trim(),
        shipment_by: document.getElementById('productShipmentBy').value.trim(),
        product_name: document.getElementById('productName').value.trim(),
        weight_kg: document.getElementById('productWeightKg').value.trim(),
        packing: document.getElementById('productPacking').value.trim(),
        price_aed: parseFloat(document.getElementById('productPriceAed').value),
    };

    try {
        if (id) {
            const result = await API.updateProduct(parseInt(id), payload);
            const idx = products.findIndex(p => p.id === parseInt(id));
            if (idx >= 0) products[idx] = result.data;
            showSuccess('Product updated');
        } else {
            const result = await API.createProduct(payload);
            products.push(result.data);
            showSuccess('Product created');
        }
        closeModal();
        productCount.textContent = `${products.length} product${products.length !== 1 ? 's' : ''}`;
        renderProducts();
    } catch (err) {
        showError(err.message);
    }
}

async function deleteProduct(id) {
    const product = products.find(p => p.id === id);
    if (!product) return;
    if (!confirm(`Delete "${product.product_name}"?`)) return;

    try {
        await API.deleteProduct(id);
        products = products.filter(p => p.id !== id);
        productCount.textContent = `${products.length} product${products.length !== 1 ? 's' : ''}`;
        renderProducts();
        showSuccess('Product deleted');
    } catch (err) {
        showError(err.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
