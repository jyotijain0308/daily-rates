const API = {
    async request(url, options = {}) {
        const response = await fetch(url, {
            headers: {
                'Accept': 'application/json',
                ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
                ...options.headers,
            },
            ...options,
        });

        let data = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            data = await response.json();
        }

        if (!response.ok) {
            const message = data?.message || `Request failed (${response.status})`;
            throw new Error(message);
        }

        return data;
    },

    getProducts(page = 1, perPage = 100) {
        return this.request(`/api/products/?page=${page}&per_page=${perPage}`);
    },

    getProductStats() {
        return this.request('/api/products/stats');
    },

    getCountries() {
        return this.request('/api/products/countries');
    },

    getManagedCountries() {
        return this.request('/api/countries/');
    },

    createCountry(country) {
        return this.request('/api/countries/', {
            method: 'POST',
            body: JSON.stringify(country),
        });
    },

    updateCountry(id, country) {
        return this.request(`/api/countries/${id}`, {
            method: 'PUT',
            body: JSON.stringify(country),
        });
    },

    uploadCountryFlag(id, file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request(`/api/countries/${id}/flag`, {
            method: 'POST',
            body: formData,
        });
    },

    deleteCountry(id) {
        return this.request(`/api/countries/${id}`, { method: 'DELETE' });
    },

    createProduct(product) {
        return this.request('/api/products/', {
            method: 'POST',
            body: JSON.stringify(product),
        });
    },

    updateProduct(id, product) {
        return this.request(`/api/products/${id}`, {
            method: 'PUT',
            body: JSON.stringify(product),
        });
    },

    updateProductImage(id, file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request(`/api/products/${id}/image`, {
            method: 'POST',
            body: formData,
        });
    },

    fetchProductImageFromPexels(id) {
        return this.request(`/api/products/${id}/image/pexels`, {
            method: 'POST',
        });
    },

    searchProductImagesFromPexels(id, options = {}) {
        return this.request(`/api/products/${id}/image/pexels/search`, {
            method: 'POST',
            body: JSON.stringify(options),
        });
    },

    selectProductImageFromPexels(id, imageUrl) {
        return this.request(`/api/products/${id}/image/pexels/select`, {
            method: 'POST',
            body: JSON.stringify({ image_url: imageUrl }),
        });
    },

    deleteProduct(id) {
        return this.request(`/api/products/${id}`, { method: 'DELETE' });
    },

    previewImport(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/api/import/preview', {
            method: 'POST',
            body: formData,
        });
    },

    previewImageImport(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/api/import/preview-image', {
            method: 'POST',
            body: formData,
        });
    },

    previewPdfImport(file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request('/api/import/preview-pdf', {
            method: 'POST',
            body: formData,
        });
    },

    saveImport(content) {
        return this.request('/api/import/save', {
            method: 'POST',
            body: JSON.stringify({ content }),
        });
    },

    getTemplate() {
        return this.request('/api/import/template');
    },

    sampleCsvUrl() {
        return '/api/import/sample';
    },

    generatePpt(options = {}) {
        return this.request('/api/generation/generate', {
            method: 'POST',
            body: JSON.stringify(options),
        });
    },

    uploadGenerationAudio(file, rightsConfirmed = false) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('rights_confirmed', rightsConfirmed ? 'true' : 'false');
        return this.request('/api/generation/audio', {
            method: 'POST',
            body: formData,
        });
    },

    getGenerationAudio() {
        return this.request('/api/generation/audio');
    },

    getGenerationJob(jobId) {
        return this.request(`/api/generation/jobs/${encodeURIComponent(jobId)}`);
    },

    cancelGenerationJob(jobId) {
        return this.request(`/api/generation/jobs/${encodeURIComponent(jobId)}/cancel`, {
            method: 'POST',
        });
    },

    getGenerationStatus() {
        return this.request('/api/generation/status');
    },

    getGenerationHistory() {
        return this.request('/api/generation/history');
    },

    getLatestPpt() {
        return this.request('/api/generation/latest');
    },

    downloadUrl(filename) {
        return `/api/generation/download/${encodeURIComponent(filename)}`;
    },

    previewUrl(filename) {
        return `/api/generation/preview/${encodeURIComponent(filename)}`;
    },
};

function formatRate(value) {
    if (value === null || value === undefined || value === '') return '—';
    return Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(isoString) {
    if (!isoString) return '—';
    const date = new Date(isoString);
    return date.toLocaleString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function calcRateChange(current, previous) {
    if (previous === null || previous === undefined || previous === 0) {
        return { text: '—', className: 'rate-neutral' };
    }
    const change = current - previous;
    const pct = ((change / previous) * 100).toFixed(2);
    const sign = change > 0 ? '+' : '';
    const className = change > 0 ? 'rate-up' : change < 0 ? 'rate-down' : 'rate-neutral';
    return { text: `${sign}${pct}%`, className };
}

document.getElementById('navToggle')?.addEventListener('click', () => {
    document.getElementById('mainNav')?.classList.toggle('open');
});
