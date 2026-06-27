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
