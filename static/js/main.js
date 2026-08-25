/**
 * Daily Inspiration — Core JavaScript Engine & Multi-Account Manager
 */

document.addEventListener('DOMContentLoaded', () => {
    initStickyNavbar();
    initMobileMenu();
    initScrollReveals();
    AccountManager.init();
    GoogleAuthManager.init();
    checkUrlAlerts();
});

/* --------------------------------------------------------------------------
   1. MULTI-ACCOUNT MANAGEMENT ENGINE
   -------------------------------------------------------------------------- */
window.AccountManager = {
    KEY_LIST: 'daily_inspiration_accounts',
    KEY_ACTIVE: 'daily_inspiration_user_email',

    init() {
        this.migrateLegacy();
        this.renderNavbar();
        this.injectModal();
        this.renderPreferencesSwitcher();
        this.validateAccountsWithBackend();
    },

    async validateAccountsWithBackend() {
        const accounts = this.getAccounts();
        if (accounts.length === 0) return;

        for (const email of accounts) {
            try {
                const res = await fetch(`/api/subscription/status?email=${encodeURIComponent(email)}`);
                if (res.ok) {
                    const data = await res.json();
                    if (!data.is_subscribed || !data.is_verified) {
                        this.removeAccount(email, true);
                    }
                }
            } catch (err) {
                // Ignore network glitch
            }
        }
    },

    getAccounts() {
        try {
            const raw = localStorage.getItem(this.KEY_LIST);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) return parsed.map(e => e.trim().toLowerCase());
            }
        } catch (e) {
            console.warn('AccountManager: Error reading accounts list', e);
        }
        return [];
    },

    setAccounts(accounts) {
        const unique = Array.from(new Set(accounts.map(e => e.trim().toLowerCase())));
        localStorage.setItem(this.KEY_LIST, JSON.stringify(unique));
    },

    getActiveAccount() {
        const list = this.getAccounts();
        const active = localStorage.getItem(this.KEY_ACTIVE);
        if (active && list.includes(active.toLowerCase())) {
            return active.toLowerCase();
        }
        if (list.length > 0) {
            localStorage.setItem(this.KEY_ACTIVE, list[0]);
            return list[0];
        }
        return null;
    },

    setActiveAccount(email) {
        if (!email) return;
        email = email.trim().toLowerCase();
        localStorage.setItem(this.KEY_ACTIVE, email);
        this.addAccount(email);
    },

    addAccount(email) {
        if (!email) return;
        email = email.trim().toLowerCase();
        let list = this.getAccounts();
        if (!list.includes(email)) {
            list.unshift(email);
            this.setAccounts(list);
        }
        localStorage.setItem(this.KEY_ACTIVE, email);
        this.renderNavbar();
        this.renderModalContent();
    },

    removeAccount(email, silent = false) {
        if (!email) return;
        email = email.trim().toLowerCase();
        let list = this.getAccounts().filter(e => e !== email);
        this.setAccounts(list);
        
        const active = localStorage.getItem(this.KEY_ACTIVE);
        if (active && active.toLowerCase() === email) {
            if (list.length > 0) {
                localStorage.setItem(this.KEY_ACTIVE, list[0]);
            } else {
                localStorage.removeItem(this.KEY_ACTIVE);
            }
        }
        
        if (!silent) {
            showToast(`Removed ${email} from this device`);
        }
        this.renderNavbar();
        this.renderModalContent();
        this.renderPreferencesSwitcher();
    },

    migrateLegacy() {
        const legacy = localStorage.getItem(this.KEY_ACTIVE);
        if (legacy && legacy.includes('@')) {
            const list = this.getAccounts();
            if (!list.includes(legacy.toLowerCase())) {
                list.unshift(legacy.toLowerCase());
                this.setAccounts(list);
            }
        }
    },

    renderNavbar() {
        const navBtn = document.getElementById('nav-account-btn') || document.getElementById('nav-subscribe-btn');
        if (!navBtn) return;

        const accounts = this.getAccounts();
        if (accounts.length > 0) {
            navBtn.id = 'nav-account-btn';
            navBtn.href = 'javascript:void(0)';
            navBtn.onclick = (e) => {
                e.preventDefault();
                AccountManager.openModal();
            };
            const label = accounts.length > 1 ? `My Accounts (${accounts.length})` : 'My Account';
            navBtn.innerHTML = `<span>👤 ${label}</span>`;
        } else {
            navBtn.id = 'nav-subscribe-btn';
            navBtn.href = '/#subscribe-form';
            navBtn.onclick = null;
            navBtn.innerHTML = `<span>✨ Subscribe Free</span>`;
        }

        const footerUnsub = document.getElementById('footer-unsub-link');
        if (footerUnsub) {
            const active = this.getActiveAccount();
            if (active) {
                footerUnsub.href = `/unsubscribe?email=${encodeURIComponent(active)}`;
            } else {
                footerUnsub.href = '/unsubscribe';
            }
        }
    },

    injectModal() {
        if (document.getElementById('account-switcher-modal')) return;

        const modalHtml = `
        <div id="account-switcher-modal" class="account-modal-backdrop" onclick="AccountManager.handleBackdropClick(event)">
            <div class="account-modal-card">
                <div class="account-modal-header">
                    <div class="account-modal-title">
                        <span>👤</span>
                        <span>Manage Linked Accounts</span>
                    </div>
                    <button type="button" class="account-modal-close" onclick="AccountManager.closeModal()" aria-label="Close modal">✕</button>
                </div>
                <div class="account-modal-body" id="account-modal-body-content">
                    <!-- Populated dynamically by renderModalContent() -->
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Escape key listener
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') AccountManager.closeModal();
        });
    },

    openModal() {
        this.injectModal();
        const modal = document.getElementById('account-switcher-modal');
        if (!modal) return;
        this.renderModalContent();
        modal.style.display = 'flex';
        modal.offsetHeight; // Force reflow
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';
    },

    closeModal() {
        const modal = document.getElementById('account-switcher-modal');
        if (!modal) return;
        modal.classList.remove('open');
        setTimeout(() => {
            if (!modal.classList.contains('open')) {
                modal.style.display = 'none';
            }
        }, 250);
        document.body.style.overflow = '';
    },

    handleBackdropClick(e) {
        if (e.target.id === 'account-switcher-modal') {
            this.closeModal();
        }
    },

    renderModalContent() {
        const container = document.getElementById('account-modal-body-content');
        if (!container) return;

        const accounts = this.getAccounts();
        const activeAccount = this.getActiveAccount();
        const currentUrlParam = new URLSearchParams(window.location.search).get('email') || '';

        let html = '';

        if (accounts.length === 0) {
            html += `
            <div style="text-align: center; padding: 24px 10px;">
                <p style="color: var(--text-muted); margin-bottom: 16px; font-size: 14.5px;">No accounts currently saved on this device.</p>
                <a href="/#subscribe-form" onclick="AccountManager.closeModal()" class="btn-open-panel" style="padding: 10px 20px;">✨ Subscribe a New Email</a>
            </div>
            `;
        } else {
            html += `<div class="account-list">`;
            accounts.forEach(email => {
                const initial = email.charAt(0).toUpperCase();
                const isCurrent = (currentUrlParam && currentUrlParam.toLowerCase() === email) || (!currentUrlParam && activeAccount === email);

                html += `
                <div class="account-item-card ${isCurrent ? 'active-account' : ''}">
                    <div class="account-info-left">
                        <div class="account-avatar-circle">${initial}</div>
                        <div class="account-details">
                            <span class="account-email-text" title="${email}">${email}</span>
                            <div class="account-status-subtext">
                                <span>Verified</span>
                                ${isCurrent ? '<span class="account-badge-current">✓ Current Active</span>' : ''}
                            </div>
                        </div>
                    </div>
                    <div class="account-actions-right">
                        <a href="/preferences?email=${encodeURIComponent(email)}" onclick="AccountManager.setActiveAccount('${email}')" class="btn-open-panel">
                            <span>Open Control Panel →</span>
                        </a>
                        <button type="button" class="btn-remove-account" onclick="AccountManager.removeAccount('${email}')" title="Remove from this browser">✕</button>
                    </div>
                </div>
                `;
            });
            html += `</div>`;
        }

        // Add/Link another account form
        html += `
        <div class="account-modal-add-form">
            <h4>+ Link / Access Another Account</h4>
            <div style="margin-bottom: 12px;">
                <button type="button" class="btn-google-auth" onclick="GoogleAuthManager.signIn(); AccountManager.closeModal();" style="padding: 10px 16px; font-size: 14px;">
                    <svg class="google-icon" viewBox="0 0 24 24" width="18" height="18">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                    </svg>
                    <span>Continue with Google</span>
                </button>
            </div>
            <div class="auth-divider" style="margin: 10px 0 12px;">
                <span class="auth-divider-line"></span>
                <span class="auth-divider-text" style="font-size: 11px;">or enter email</span>
                <span class="auth-divider-line"></span>
            </div>
            <form onsubmit="AccountManager.handleLinkAccountForm(event)" class="account-add-input-group">
                <input type="email" id="modal-add-email-input" class="account-add-input" placeholder="Enter another email address..." required autocomplete="email">
                <button type="submit" class="btn-add-account">Access Panel</button>
            </form>
        </div>
        `;

        container.innerHTML = html;
    },

    handleLinkAccountForm(e) {
        e.preventDefault();
        const input = document.getElementById('modal-add-email-input');
        if (!input || !input.value.trim()) return;

        const email = input.value.trim().toLowerCase();
        this.addAccount(email);
        this.closeModal();
        window.location.href = `/preferences?email=${encodeURIComponent(email)}`;
    },

    renderPreferencesSwitcher() {
        const switcherContainer = document.getElementById('quick-account-switcher-placeholder');
        if (!switcherContainer) return;

        const accounts = this.getAccounts();
        if (accounts.length <= 1) {
            switcherContainer.innerHTML = '';
            switcherContainer.style.display = 'none';
            return;
        }

        const currentEmail = (new URLSearchParams(window.location.search).get('email') || '').toLowerCase();

        let pillsHtml = accounts.map(email => {
            const isCurrent = email === currentEmail;
            return `
            <a href="/preferences?email=${encodeURIComponent(email)}" 
               onclick="AccountManager.setActiveAccount('${email}')" 
               class="account-switch-pill ${isCurrent ? 'current' : ''}">
               <span>👤 ${email}</span>
               ${isCurrent ? '<small style="opacity:0.9;">(Active)</small>' : ''}
            </a>
            `;
        }).join('');

        switcherContainer.innerHTML = `
        <div class="quick-account-switcher-bar">
            <div class="quick-switcher-label">
                <span>🔄 Switch Account:</span>
            </div>
            <div class="quick-account-pills">
                ${pillsHtml}
                <button type="button" onclick="AccountManager.openModal()" class="btn-manage-all-accounts">+ Manage Accounts</button>
            </div>
        </div>
        `;
        switcherContainer.style.display = 'block';
    }
};

/* --------------------------------------------------------------------------
   2. NAVBAR & SCROLL BEHAVIOR
   -------------------------------------------------------------------------- */
function initStickyNavbar() {
    const header = document.getElementById('site-header');
    if (!header) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 30) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    }, { passive: true });
}

function initMobileMenu() {
    const toggle = document.getElementById('mobile-toggle');
    const nav = document.getElementById('main-nav');
    if (!toggle || !nav) return;

    toggle.addEventListener('click', () => {
        toggle.classList.toggle('open');
        nav.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
        if (!toggle.contains(e.target) && !nav.contains(e.target) && nav.classList.contains('open')) {
            toggle.classList.remove('open');
            nav.classList.remove('open');
        }
    });
}

function initScrollReveals() {
    const revealElements = document.querySelectorAll('.reveal-up, .reveal-fade');
    if (!revealElements.length) return;

    if (!('IntersectionObserver' in window)) {
        revealElements.forEach(el => el.classList.add('is-visible'));
        return;
    }

    document.documentElement.classList.add('js-enabled');

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                obs.unobserve(entry.target);
            }
        });
    }, {
        root: null,
        rootMargin: '0px 0px 50px 0px',
        threshold: 0.05
    });

    revealElements.forEach(el => observer.observe(el));
}

/* --------------------------------------------------------------------------
   3. GLOBAL TOAST ALERTS & NOTIFICATIONS
   -------------------------------------------------------------------------- */
function showToast(message) {
    let toast = document.getElementById('global-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'global-toast';
        toast.className = 'toast-notification';
        document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3200);
}

function showMessage(elementId, text, type = 'success') {
    const msgEl = document.getElementById(elementId);
    if (!msgEl) return;

    msgEl.className = `message ${type}`;
    msgEl.textContent = text;
    msgEl.style.display = 'block';

    if (type === 'success') {
        setTimeout(() => {
            msgEl.style.display = 'none';
        }, 5000);
    }
}

function checkUrlAlerts() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('subscribed') === 'true' || params.get('welcome') === 'true') {
        showToast('🎉 You are all set! Welcome to Daily Inspiration ✨');
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.get('preferences_saved') === 'true') {
        showToast('✓ Preferences updated successfully! ✨');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

/* --------------------------------------------------------------------------
   4. GOOGLE AUTHENTICATION MANAGER (Strict Google Identity Services OAuth)
   -------------------------------------------------------------------------- */
window.GoogleAuthManager = {
    clientId: '',
    isConfigured: false,
    isInitialized: false,

    async init() {
        try {
            const res = await fetch('/api/subscription/google-client-id');
            if (res.ok) {
                const data = await res.json();
                this.clientId = data.client_id || '';
                this.isConfigured = data.is_configured;
            }
        } catch (e) {
            console.warn('GoogleAuthManager: Failed to fetch client configuration', e);
        }

        this.setupGIS();
    },

    setupGIS() {
        if (typeof google !== 'undefined' && google.accounts && google.accounts.id && this.clientId) {
            try {
                google.accounts.id.initialize({
                    client_id: this.clientId,
                    callback: (response) => this.handleCredentialResponse(response),
                    auto_select: false,
                    cancel_on_tap_outside: true
                });
                this.isInitialized = true;

                // Render hidden GIS standard button for programmatic click trigger
                const heroBtn = document.getElementById('google-hidden-btn-hero');
                if (heroBtn) {
                    google.accounts.id.renderButton(heroBtn, {
                        type: 'standard',
                        theme: 'outline',
                        size: 'large'
                    });
                }
            } catch (err) {
                console.warn('GoogleAuthManager: GIS initialization error', err);
            }
        } else if (!this.isInitialized && this.clientId) {
            // Check again if GIS script loads slightly after DOMContentLoaded
            setTimeout(() => {
                if (typeof google !== 'undefined' && google.accounts && this.clientId) {
                    this.setupGIS();
                }
            }, 1000);
        }
    },

    signIn() {
        if (!this.isConfigured || !this.clientId) {
            this.showSetupNotice();
            return;
        }

        if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
            if (!this.isInitialized) {
                this.setupGIS();
            }

            try {
                // Trigger GIS One-Tap prompt or click the rendered Google button
                google.accounts.id.prompt((notification) => {
                    if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                        const btn = document.querySelector('#google-hidden-btn-hero div[role="button"]');
                        if (btn) btn.click();
                    }
                });
            } catch (e) {
                const btn = document.querySelector('#google-hidden-btn-hero div[role="button"]');
                if (btn) btn.click();
            }
        } else {
            showToast('Loading Google Services, please try again in a moment...');
        }
    },

    async handleCredentialResponse(response) {
        if (!response || !response.credential) {
            showToast('Google sign-in was cancelled.');
            return;
        }

        showToast('Verifying Google credentials with backend... ⏳');

        try {
            const res = await fetch('/api/subscription/google-auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential: response.credential })
            });

            const data = await res.json();

            if (res.ok && data.success) {
                AccountManager.addAccount(data.email);
                showToast(data.message || 'Verified with Google! ✨');

                setTimeout(() => {
                    if (data.is_new) {
                        window.location.href = `/success?email=${encodeURIComponent(data.email)}&google=true`;
                    } else {
                        window.location.href = `/preferences?email=${encodeURIComponent(data.email)}&google=true`;
                    }
                }, 700);
            } else {
                showToast(data.detail || 'Google authentication failed.');
            }
        } catch (err) {
            showToast('Network error during Google sign-in.');
        }
    },

    showSetupNotice() {
        let modal = document.getElementById('google-setup-notice-modal');
        if (!modal) {
            const html = `
            <div id="google-setup-notice-modal" class="account-modal-backdrop" onclick="if(event.target.id==='google-setup-notice-modal') this.style.display='none'">
                <div class="account-modal-card" style="max-width: 480px;">
                    <div class="account-modal-header">
                        <div class="account-modal-title">
                            <svg class="google-icon" viewBox="0 0 24 24" width="22" height="22" style="vertical-align: middle;">
                                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                            </svg>
                            <span>Google OAuth Configuration</span>
                        </div>
                        <button type="button" class="account-modal-close" onclick="document.getElementById('google-setup-notice-modal').style.display='none'">✕</button>
                    </div>
                    <div class="account-modal-body" style="padding: 22px 24px;">
                        <p style="font-size: 15px; color: var(--text-primary); margin-bottom: 14px; line-height: 1.5;">
                            <strong>Google Client ID Required:</strong>
                        </p>
                        <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 16px; line-height: 1.5;">
                            To authenticate real Google accounts, configure your Google OAuth Client ID in your <code>.env</code> file:
                        </p>
                        <div style="background: #f1f5f9; padding: 12px 14px; border-radius: 8px; font-family: monospace; font-size: 13px; color: #0f172a; word-break: break-all; margin-bottom: 16px; border: 1px solid #e2e8f0;">
                            GOOGLE_CLIENT_ID=your-id.apps.googleusercontent.com
                        </div>
                        <p style="font-size: 13px; color: var(--text-muted); line-height: 1.5; margin-bottom: 20px;">
                            📌 You can generate this for free in <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color: var(--color-primary); text-decoration: underline;">Google Cloud Console → APIs & Services → Credentials</a>.
                        </p>
                        <button type="button" class="btn-primary" onclick="document.getElementById('google-setup-notice-modal').style.display='none'" style="width: 100%;">
                            <span>Got it</span>
                        </button>
                    </div>
                </div>
            </div>
            `;
            document.body.insertAdjacentHTML('beforeend', html);
            modal = document.getElementById('google-setup-notice-modal');
        }
        modal.style.display = 'flex';
        modal.classList.add('open');
    }
};
