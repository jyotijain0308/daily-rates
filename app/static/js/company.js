let currentCompany = null;

const companyForm = document.getElementById('companyForm');
const companyStatus = document.getElementById('companyStatus');
const reloadCompanyBtn = document.getElementById('reloadCompanyBtn');
const saveCompanyBtn = document.getElementById('saveCompanyBtn');
const youtubeStatus = document.getElementById('youtubeStatus');
const youtubeConnectionMessage = document.getElementById('youtubeConnectionMessage');
const connectYouTubeBtn = document.getElementById('connectYouTubeBtn');
const disconnectYouTubeBtn = document.getElementById('disconnectYouTubeBtn');
const facebookStatus = document.getElementById('facebookStatus');
const facebookConnectionMessage = document.getElementById('facebookConnectionMessage');
const connectFacebookBtn = document.getElementById('connectFacebookBtn');
const disconnectFacebookBtn = document.getElementById('disconnectFacebookBtn');
const instagramStatus = document.getElementById('instagramStatus');
const instagramConnectionMessage = document.getElementById('instagramConnectionMessage');
const xStatus = document.getElementById('xStatus');
const xConnectionMessage = document.getElementById('xConnectionMessage');
const connectXBtn = document.getElementById('connectXBtn');
const disconnectXBtn = document.getElementById('disconnectXBtn');
const linkedinPersonalStatus = document.getElementById('linkedinPersonalStatus');
const linkedinPersonalConnectionMessage = document.getElementById('linkedinPersonalConnectionMessage');
const connectLinkedInPersonalBtn = document.getElementById('connectLinkedInPersonalBtn');
const disconnectLinkedInPersonalBtn = document.getElementById('disconnectLinkedInPersonalBtn');
const linkedinPageStatus = document.getElementById('linkedinPageStatus');
const linkedinPageConnectionMessage = document.getElementById('linkedinPageConnectionMessage');
const connectLinkedInPageBtn = document.getElementById('connectLinkedInPageBtn');
const disconnectLinkedInPageBtn = document.getElementById('disconnectLinkedInPageBtn');

const fields = {
    name: document.getElementById('companyName'),
    subtitle: document.getElementById('companySubtitle'),
    default_country: document.getElementById('defaultCountry'),
    address: document.getElementById('companyAddress'),
    website: document.getElementById('companyWebsite'),
    company_logo_image: document.getElementById('companyLogoImage'),
    destination_logo_image: document.getElementById('destinationLogoImage'),
    currency: document.getElementById('companyCurrency'),
    rate_display_format: document.getElementById('rateDisplayFormat'),
    import_price_deduction_percent: document.getElementById('importPriceDeductionPercent'),
    social_post_description: document.getElementById('socialPostDescription'),
};

const assetInputs = {
    company_logo_image: document.getElementById('companyLogoInput'),
    destination_logo_image: document.getElementById('destinationLogoInput'),
};
const assetBrowseButtons = {
    company_logo_image: document.getElementById('browseCompanyLogoBtn'),
    destination_logo_image: document.getElementById('browseDestinationLogoBtn'),
};
const assetFileNames = {
    company_logo_image: document.getElementById('companyLogoFileName'),
    destination_logo_image: document.getElementById('destinationLogoFileName'),
};
const assetPreviewImages = {
    company_logo_image: document.getElementById('companyLogoPreviewImg'),
    destination_logo_image: document.getElementById('destinationLogoPreviewImg'),
};
const assetPreviewEmpty = {
    company_logo_image: document.getElementById('companyLogoPreviewEmpty'),
    destination_logo_image: document.getElementById('destinationLogoPreviewEmpty'),
};
const selectedAssetFiles = {
    company_logo_image: null,
    destination_logo_image: null,
};
const selectedAssetPreviewUrls = {
    company_logo_image: null,
    destination_logo_image: null,
};

companyForm.addEventListener('submit', saveCompany);
reloadCompanyBtn.addEventListener('click', loadCompany);
connectYouTubeBtn.addEventListener('click', connectYouTube);
disconnectYouTubeBtn.addEventListener('click', disconnectYouTube);
connectFacebookBtn.addEventListener('click', connectFacebook);
disconnectFacebookBtn.addEventListener('click', disconnectFacebook);
connectXBtn.addEventListener('click', connectX);
disconnectXBtn.addEventListener('click', disconnectX);
connectLinkedInPersonalBtn.addEventListener('click', connectLinkedInPersonal);
disconnectLinkedInPersonalBtn.addEventListener('click', disconnectLinkedInPersonal);
connectLinkedInPageBtn.addEventListener('click', connectLinkedInPage);
disconnectLinkedInPageBtn.addEventListener('click', disconnectLinkedInPage);
Object.keys(assetBrowseButtons).forEach(field => {
    assetBrowseButtons[field].addEventListener('click', () => assetInputs[field].click());
    assetInputs[field].addEventListener('change', event => handleAssetSelected(field, event));
});

loadCompany();

async function loadCompany() {
    setLoading(true);
    try {
        const result = await API.getCurrentCompany();
        currentCompany = result.data;
        fillCompanyForm(currentCompany);
        companyStatus.textContent = currentCompany.is_active ? 'Active' : 'Inactive';
        companyStatus.className = currentCompany.is_active
            ? 'status-pill status-active'
            : 'status-pill status-inactive';
    } catch (err) {
        showError(err.message);
        companyStatus.textContent = 'Error';
        companyStatus.className = 'status-pill status-inactive';
    } finally {
        setLoading(false);
    }
    await loadYouTubeStatus();
    await loadFacebookStatus();
    await loadInstagramStatus();
    await loadXStatus();
    await loadLinkedInPersonalStatus();
    await loadLinkedInPageStatus();
}

function fillCompanyForm(company) {
    const settings = company.settings || {};
    fields.name.value = company.name || '';
    fields.subtitle.value = settings.subtitle || '';
    fields.default_country.value = settings.default_country || '';
    fields.address.value = settings.address || '';
    fields.website.value = settings.website || '';
    fields.company_logo_image.value = settings.company_logo_image || '';
    fields.destination_logo_image.value = settings.destination_logo_image || '';
    setAssetPreview('company_logo_image', settings.company_logo_url || '');
    setAssetPreview('destination_logo_image', settings.destination_logo_url || '');
    resetAssetSelection('company_logo_image', false);
    resetAssetSelection('destination_logo_image', false);
    fields.currency.value = settings.currency || '';
    fields.rate_display_format.value = settings.rate_display_format || '';
    fields.import_price_deduction_percent.value = settings.import_price_deduction_percent ?? 15;
    fields.social_post_description.value = settings.social_post_description || '';
}

async function saveCompany(e) {
    e.preventDefault();
    if (!currentCompany?.id) {
        showError('Company could not be loaded');
        return;
    }

    setLoading(true);
    try {
        await uploadSelectedAssets();
    } catch (err) {
        setLoading(false);
        showError(err.message);
        return;
    }

    const payload = {
        name: fields.name.value.trim(),
        subtitle: fields.subtitle.value.trim(),
        default_country: fields.default_country.value.trim(),
        address: fields.address.value.trim(),
        website: fields.website.value.trim(),
        company_logo_image: fields.company_logo_image.value.trim(),
        destination_logo_image: fields.destination_logo_image.value.trim(),
        currency: fields.currency.value.trim().toUpperCase(),
        rate_display_format: fields.rate_display_format.value.trim(),
        import_price_deduction_percent: parseFloat(fields.import_price_deduction_percent.value),
        social_post_description: fields.social_post_description.value.trim(),
    };

    if (!payload.name || !payload.subtitle || !payload.default_country || !payload.address) {
        showError('Company name, subtitle, default country, and address are required');
        return;
    }

    if (
        !payload.currency ||
        !payload.rate_display_format ||
        Number.isNaN(payload.import_price_deduction_percent)
    ) {
        showError('Currency, rate display format, and deduction are required');
        return;
    }

    try {
        const result = await API.updateCompanySettings(currentCompany.id, payload);
        currentCompany = result.data;
        fillCompanyForm(currentCompany);
        showSuccess('Company settings saved');
    } catch (err) {
        showError(err.message);
    } finally {
        setLoading(false);
    }
}

function setLoading(isLoading) {
    saveCompanyBtn.disabled = isLoading;
    reloadCompanyBtn.disabled = isLoading;
    connectYouTubeBtn.disabled = isLoading;
    disconnectYouTubeBtn.disabled = isLoading;
    connectFacebookBtn.disabled = isLoading;
    disconnectFacebookBtn.disabled = isLoading;
    connectXBtn.disabled = isLoading;
    disconnectXBtn.disabled = isLoading;
    connectLinkedInPersonalBtn.disabled = isLoading;
    disconnectLinkedInPersonalBtn.disabled = isLoading;
    connectLinkedInPageBtn.disabled = isLoading;
    disconnectLinkedInPageBtn.disabled = isLoading;
    Object.values(assetBrowseButtons).forEach(button => {
        button.disabled = isLoading;
    });
}

async function loadYouTubeStatus() {
    try {
        const result = await API.getYouTubeStatus();
        const status = result.data || {};
        if (!status.configured) {
            youtubeStatus.textContent = 'Setup needed';
            youtubeStatus.className = 'status-pill status-inactive';
            youtubeConnectionMessage.textContent = 'Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env before connecting.';
            connectYouTubeBtn.style.display = 'inline-flex';
            disconnectYouTubeBtn.style.display = 'none';
            return;
        }

        if (status.connected) {
            youtubeStatus.textContent = 'Connected';
            youtubeStatus.className = 'status-pill status-active';
            youtubeConnectionMessage.textContent = status.external_account_name
                ? `Connected to ${status.external_account_name}.`
                : 'YouTube channel connected.';
            connectYouTubeBtn.style.display = 'none';
            disconnectYouTubeBtn.style.display = 'inline-flex';
        } else {
            youtubeStatus.textContent = 'Not connected';
            youtubeStatus.className = 'status-pill status-inactive';
            youtubeConnectionMessage.textContent = 'Connect a company YouTube channel to publish generated MP4 videos.';
            connectYouTubeBtn.style.display = 'inline-flex';
            disconnectYouTubeBtn.style.display = 'none';
        }
    } catch (err) {
        youtubeStatus.textContent = 'Error';
        youtubeStatus.className = 'status-pill status-inactive';
        youtubeConnectionMessage.textContent = err.message;
    }
}

async function connectYouTube() {
    try {
        const result = await API.getYouTubeConnectUrl();
        window.location.href = result.data.auth_url;
    } catch (err) {
        showError(err.message);
    }
}

async function disconnectYouTube() {
    if (!confirm('Disconnect YouTube for this company?')) return;

    try {
        await API.disconnectYouTube();
        showSuccess('YouTube disconnected');
        await loadYouTubeStatus();
    } catch (err) {
        showError(err.message);
    }
}

async function loadFacebookStatus() {
    try {
        const result = await API.getFacebookStatus();
        const status = result.data || {};
        if (!status.configured) {
            facebookStatus.textContent = 'Setup needed';
            facebookStatus.className = 'status-pill status-inactive';
            facebookConnectionMessage.textContent = 'Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in .env before connecting.';
            connectFacebookBtn.style.display = 'inline-flex';
            disconnectFacebookBtn.style.display = 'none';
            return;
        }

        if (status.connected) {
            facebookStatus.textContent = 'Connected';
            facebookStatus.className = 'status-pill status-active';
            facebookConnectionMessage.textContent = status.external_account_name
                ? `Connected to Page ${status.external_account_name}.`
                : 'Facebook Page connected.';
            connectFacebookBtn.style.display = 'none';
            disconnectFacebookBtn.style.display = 'inline-flex';
        } else {
            facebookStatus.textContent = 'Not connected';
            facebookStatus.className = 'status-pill status-inactive';
            facebookConnectionMessage.textContent = 'Connect a Facebook Page to publish generated MP4 videos. Personal Facebook sharing stays manual.';
            connectFacebookBtn.style.display = 'inline-flex';
            disconnectFacebookBtn.style.display = 'none';
        }
    } catch (err) {
        facebookStatus.textContent = 'Error';
        facebookStatus.className = 'status-pill status-inactive';
        facebookConnectionMessage.textContent = err.message;
    }
}

async function loadInstagramStatus() {
    try {
        const result = await API.getInstagramStatus();
        const status = result.data || {};
        if (!status.facebook_connected) {
            instagramStatus.textContent = 'Needs Facebook';
            instagramStatus.className = 'status-pill status-inactive';
            instagramConnectionMessage.textContent = 'Connect Facebook Page first, then link an Instagram professional account to that Page.';
            return;
        }
        if (!status.connected) {
            instagramStatus.textContent = 'No IG account';
            instagramStatus.className = 'status-pill status-inactive';
            instagramConnectionMessage.textContent = status.message || 'No Instagram professional account is linked to the connected Facebook Page.';
            return;
        }
        if (!status.public_base_url_configured) {
            instagramStatus.textContent = 'Setup needed';
            instagramStatus.className = 'status-pill status-inactive';
            instagramConnectionMessage.textContent = 'Set SOCIAL_PUBLIC_BASE_URL to publish MP4 videos to Instagram.';
            return;
        }

        instagramStatus.textContent = 'Connected';
        instagramStatus.className = 'status-pill status-active';
        instagramConnectionMessage.textContent = status.external_account_name
            ? `Connected to Instagram @${status.external_account_name}.`
            : 'Instagram professional account connected.';
    } catch (err) {
        instagramStatus.textContent = 'Error';
        instagramStatus.className = 'status-pill status-inactive';
        instagramConnectionMessage.textContent = err.message;
    }
}

async function connectFacebook() {
    try {
        const result = await API.getFacebookConnectUrl();
        window.location.href = result.data.auth_url;
    } catch (err) {
        showError(err.message);
    }
}

async function disconnectFacebook() {
    if (!confirm('Disconnect Facebook for this company?')) return;

    try {
        await API.disconnectFacebook();
        showSuccess('Facebook disconnected');
        await loadFacebookStatus();
        await loadInstagramStatus();
    } catch (err) {
        showError(err.message);
    }
}

async function loadXStatus() {
    try {
        const result = await API.getXStatus();
        const status = result.data || {};
        if (!status.configured) {
            xStatus.textContent = 'Setup needed';
            xStatus.className = 'status-pill status-inactive';
            xConnectionMessage.textContent = 'Set X_CLIENT_ID in .env before connecting. Add X_CLIENT_SECRET for confidential apps.';
            connectXBtn.style.display = 'inline-flex';
            disconnectXBtn.style.display = 'none';
            return;
        }

        if (status.connected) {
            xStatus.textContent = 'Connected';
            xStatus.className = 'status-pill status-active';
            xConnectionMessage.textContent = status.external_account_name
                ? `Connected to ${status.external_account_name}.`
                : 'X account connected.';
            connectXBtn.style.display = 'none';
            disconnectXBtn.style.display = 'inline-flex';
        } else {
            xStatus.textContent = 'Not connected';
            xStatus.className = 'status-pill status-inactive';
            xConnectionMessage.textContent = 'Connect X to publish generated MP4 videos as Posts.';
            connectXBtn.style.display = 'inline-flex';
            disconnectXBtn.style.display = 'none';
        }
    } catch (err) {
        xStatus.textContent = 'Error';
        xStatus.className = 'status-pill status-inactive';
        xConnectionMessage.textContent = err.message;
    }
}

async function connectX() {
    try {
        const result = await API.getXConnectUrl();
        window.location.href = result.data.auth_url;
    } catch (err) {
        showError(err.message);
    }
}

async function disconnectX() {
    if (!confirm('Disconnect X for this company?')) return;

    try {
        await API.disconnectX();
        showSuccess('X disconnected');
        await loadXStatus();
    } catch (err) {
        showError(err.message);
    }
}

async function loadLinkedInPersonalStatus() {
    await loadLinkedInTargetStatus({
        statusEl: linkedinPersonalStatus,
        messageEl: linkedinPersonalConnectionMessage,
        connectBtn: connectLinkedInPersonalBtn,
        disconnectBtn: disconnectLinkedInPersonalBtn,
        request: () => API.getLinkedInPersonalStatus(),
        connectedMessage: name => name ? `Connected to ${name}.` : 'LinkedIn personal profile connected.',
        disconnectedMessage: 'Connect a LinkedIn profile to publish generated MP4 videos personally.',
    });
}

async function loadLinkedInPageStatus() {
    await loadLinkedInTargetStatus({
        statusEl: linkedinPageStatus,
        messageEl: linkedinPageConnectionMessage,
        connectBtn: connectLinkedInPageBtn,
        disconnectBtn: disconnectLinkedInPageBtn,
        request: () => API.getLinkedInPageStatus(),
        connectedMessage: name => name ? `Connected to Page ${name}.` : 'LinkedIn Page connected.',
        disconnectedMessage: 'Connect with a LinkedIn admin account to publish generated MP4 videos to a Page.',
    });
}

async function loadLinkedInTargetStatus(options) {
    try {
        const result = await options.request();
        const status = result.data || {};
        if (!status.configured) {
            options.statusEl.textContent = 'Setup needed';
            options.statusEl.className = 'status-pill status-inactive';
            options.messageEl.textContent = 'Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env before connecting.';
            options.connectBtn.style.display = 'inline-flex';
            options.disconnectBtn.style.display = 'none';
            return;
        }

        if (status.connected) {
            options.statusEl.textContent = 'Connected';
            options.statusEl.className = 'status-pill status-active';
            options.messageEl.textContent = options.connectedMessage(status.external_account_name);
            options.connectBtn.style.display = 'none';
            options.disconnectBtn.style.display = 'inline-flex';
        } else {
            options.statusEl.textContent = 'Not connected';
            options.statusEl.className = 'status-pill status-inactive';
            options.messageEl.textContent = options.disconnectedMessage;
            options.connectBtn.style.display = 'inline-flex';
            options.disconnectBtn.style.display = 'none';
        }
    } catch (err) {
        options.statusEl.textContent = 'Error';
        options.statusEl.className = 'status-pill status-inactive';
        options.messageEl.textContent = err.message;
    }
}

async function connectLinkedInPersonal() {
    try {
        const result = await API.getLinkedInPersonalConnectUrl();
        window.location.href = result.data.auth_url;
    } catch (err) {
        showError(err.message);
    }
}

async function connectLinkedInPage() {
    try {
        const result = await API.getLinkedInPageConnectUrl();
        window.location.href = result.data.auth_url;
    } catch (err) {
        showError(err.message);
    }
}

async function disconnectLinkedInPersonal() {
    if (!confirm('Disconnect LinkedIn personal profile for this company?')) return;

    try {
        await API.disconnectLinkedInPersonal();
        showSuccess('LinkedIn personal profile disconnected');
        await loadLinkedInPersonalStatus();
    } catch (err) {
        showError(err.message);
    }
}

async function disconnectLinkedInPage() {
    if (!confirm('Disconnect LinkedIn Page for this company?')) return;

    try {
        await API.disconnectLinkedInPage();
        showSuccess('LinkedIn Page disconnected');
        await loadLinkedInPageStatus();
    } catch (err) {
        showError(err.message);
    }
}

function handleAssetSelected(field, event) {
    const file = event.target.files[0];
    if (!file) {
        resetAssetSelection(field, true);
        return;
    }

    if (!file.type.startsWith('image/')) {
        resetAssetSelection(field, true);
        showError('Please select an image file');
        return;
    }

    selectedAssetFiles[field] = file;
    assetFileNames[field].textContent = file.name;

    if (selectedAssetPreviewUrls[field]) {
        URL.revokeObjectURL(selectedAssetPreviewUrls[field]);
    }
    selectedAssetPreviewUrls[field] = URL.createObjectURL(file);
    setAssetPreview(field, selectedAssetPreviewUrls[field]);
}

function resetAssetSelection(field, clearPreview) {
    selectedAssetFiles[field] = null;
    assetInputs[field].value = '';
    assetFileNames[field].textContent = 'No file selected';
    if (selectedAssetPreviewUrls[field]) {
        URL.revokeObjectURL(selectedAssetPreviewUrls[field]);
        selectedAssetPreviewUrls[field] = null;
    }
    if (clearPreview) {
        setAssetPreview(field, '');
    }
}

function setAssetPreview(field, src) {
    if (src) {
        assetPreviewImages[field].src = src;
        assetPreviewImages[field].style.display = 'block';
        assetPreviewEmpty[field].style.display = 'none';
    } else {
        assetPreviewImages[field].src = '';
        assetPreviewImages[field].style.display = 'none';
        assetPreviewEmpty[field].style.display = 'inline-flex';
    }
}

async function uploadSelectedAssets() {
    for (const [field, file] of Object.entries(selectedAssetFiles)) {
        if (!file) continue;

        const result = await API.uploadCompanyAsset(currentCompany.id, field, file);
        currentCompany = result.data;
        const settings = currentCompany.settings || {};
        fields[field].value = settings[field] || '';
        setAssetPreview(field, settings[field === 'company_logo_image' ? 'company_logo_url' : 'destination_logo_url'] || '');
        resetAssetSelection(field, false);
    }
}
