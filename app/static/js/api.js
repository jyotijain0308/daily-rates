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
            const error = new Error(message);
            error.status = response.status;
            error.data = data;
            throw error;
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

    getCurrentCompany() {
        return this.request('/api/companies/current');
    },

    updateCompanySettings(id, payload) {
        return this.request(`/api/companies/${id}/settings`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
    },

    uploadCompanyAsset(id, field, file) {
        const formData = new FormData();
        formData.append('file', file);
        return this.request(`/api/companies/${id}/assets/${encodeURIComponent(field)}`, {
            method: 'POST',
            body: formData,
        });
    },

    getSocialAppConfigs() {
        return this.request('/api/system/social-app-configs');
    },

    updateSocialAppConfig(provider, settings) {
        return this.request(`/api/system/social-app-configs/${encodeURIComponent(provider)}`, {
            method: 'PUT',
            body: JSON.stringify({ settings }),
        });
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

    // PDF and image imports are intentionally disabled. CSV import remains active.
    // previewImageImport(file) {
    //     const formData = new FormData();
    //     formData.append('file', file);
    //     return this.request('/api/import/preview-image', {
    //         method: 'POST',
    //         body: formData,
    //     });
    // },
    //
    // previewPdfImport(file) {
    //     const formData = new FormData();
    //     formData.append('file', file);
    //     return this.request('/api/import/preview-pdf', {
    //         method: 'POST',
    //         body: formData,
    //     });
    // },

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

    getGenerationShareMetadata(filename) {
        return this.request(`/api/generation/share-metadata/${encodeURIComponent(filename)}`);
    },

    getYouTubeStatus() {
        return this.request('/api/social/youtube/status');
    },

    getYouTubeConnectUrl() {
        return this.request('/api/social/youtube/connect-url');
    },

    disconnectYouTube() {
        return this.request('/api/social/youtube/disconnect', {
            method: 'POST',
        });
    },

    publishYouTube(payload) {
        return this.request('/api/social/youtube/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    getFacebookStatus() {
        return this.request('/api/social/facebook/status');
    },

    getFacebookConnectUrl() {
        return this.request('/api/social/facebook/connect-url');
    },

    disconnectFacebook() {
        return this.request('/api/social/facebook/disconnect', {
            method: 'POST',
        });
    },

    publishFacebook(payload) {
        return this.request('/api/social/facebook/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    getInstagramStatus() {
        return this.request('/api/social/instagram/status');
    },

    publishInstagram(payload) {
        return this.request('/api/social/instagram/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    getXStatus() {
        return this.request('/api/social/x/status');
    },

    getXConnectUrl() {
        return this.request('/api/social/x/connect-url');
    },

    disconnectX() {
        return this.request('/api/social/x/disconnect', {
            method: 'POST',
        });
    },

    publishX(payload) {
        return this.request('/api/social/x/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    getLinkedInStatus() {
        return this.request('/api/social/linkedin/status');
    },

    getLinkedInPersonalStatus() {
        return this.request('/api/social/linkedin/personal/status');
    },

    getLinkedInPageStatus() {
        return this.request('/api/social/linkedin/page/status');
    },

    getLinkedInConnectUrl() {
        return this.request('/api/social/linkedin/connect-url');
    },

    getLinkedInPersonalConnectUrl() {
        return this.request('/api/social/linkedin/personal/connect-url');
    },

    getLinkedInPageConnectUrl() {
        return this.request('/api/social/linkedin/page/connect-url');
    },

    disconnectLinkedIn() {
        return this.request('/api/social/linkedin/disconnect', {
            method: 'POST',
        });
    },

    disconnectLinkedInPersonal() {
        return this.request('/api/social/linkedin/personal/disconnect', {
            method: 'POST',
        });
    },

    disconnectLinkedInPage() {
        return this.request('/api/social/linkedin/page/disconnect', {
            method: 'POST',
        });
    },

    publishLinkedIn(payload) {
        return this.request('/api/social/linkedin/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    publishLinkedInPersonal(payload) {
        return this.request('/api/social/linkedin/personal/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    publishLinkedInPage(payload) {
        return this.request('/api/social/linkedin/page/publish', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    },

    generateSocialHashtags(payload) {
        return this.request('/api/social/hashtags', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
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
