let products = [];

const productsBody = document.getElementById('productsBody');
const productSearch = document.getElementById('productSearch');
const productCount = document.getElementById('productCount');
const productModal = document.getElementById('productModal');
const productForm = document.getElementById('productForm');
const imagePreviewModal = document.getElementById('imagePreviewModal');
const imagePreviewImg = document.getElementById('imagePreviewImg');
const imagePreviewTitle = document.getElementById('imagePreviewTitle');
const productImageInput = document.getElementById('productImageInput');
const replaceImageBtn = document.getElementById('replaceImageBtn');
let selectedImageProductId = null;

document.getElementById('addProductBtn').addEventListener('click', () => openModal());
document.getElementById('closeModalBtn').addEventListener('click', closeModal);
document.getElementById('cancelModalBtn').addEventListener('click', closeModal);
document.getElementById('closeImagePreviewBtn').addEventListener('click', closeImagePreview);
replaceImageBtn.addEventListener('click', () => {
    if (selectedImageProductId) openImageUpload(selectedImageProductId);
});
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
        productCount.textContent = `${result.pagination.total} product${result.pagination.total !== 1 ? 's' : ''}`;
        renderProducts();
    } catch (err) {
        productsBody.innerHTML = `<tr><td colspan="9" class="empty-state">${err.message}</td></tr>`;
        showError(err.message);
    }
}

function renderProducts() {
    const query = productSearch.value.toLowerCase().trim();
    const filtered = products.filter(p =>
        p.product_name.toLowerCase().includes(query) ||
        p.country_of_origin.toLowerCase().includes(query) ||
        p.shipment_by.toLowerCase().includes(query)
    );

    if (filtered.length === 0) {
        productsBody.innerHTML = '<tr><td colspan="9" class="empty-state">No products found. Import CSV or add a product.</td></tr>';
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
                <td class="editable" data-field="weight_kg">${Number(p.weight_kg).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
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
        btn.addEventListener('click', () => openImageUpload(parseInt(btn.dataset.id)));
    });

    productsBody.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteProduct(parseInt(btn.dataset.id)));
    });
}

function openImagePreview(product) {
    if (!product.image_url) return;

    selectedImageProductId = product.id;
    imagePreviewTitle.textContent = product.product_name;
    imagePreviewImg.src = product.image_url;
    imagePreviewImg.alt = product.product_name;
    imagePreviewModal.style.display = 'flex';
}

function closeImagePreview() {
    imagePreviewModal.style.display = 'none';
    imagePreviewImg.src = '';
    imagePreviewImg.alt = '';
    selectedImageProductId = null;
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
    input.type = ['serial_no', 'weight_kg', 'price_aed'].includes(field) ? 'number' : 'text';
    if (field === 'weight_kg' || field === 'price_aed') input.step = '0.01';
    if (field === 'serial_no') input.step = '1';

    cell.textContent = '';
    cell.appendChild(input);
    input.focus();
    input.select();

    const save = async () => {
        const newValue = input.value.trim();
        const payload = {
            [field]: ['weight_kg', 'price_aed'].includes(field)
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
        weight_kg: parseFloat(document.getElementById('productWeightKg').value),
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
