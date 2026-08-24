/**
 * Daily Inspiration — Core JavaScript Engine & Multi-Account Manager
 */

document.addEventListener('DOMContentLoaded', () => {
    initStickyNavbar();
    initMobileMenu();
    initScrollReveals();
    AccountManager.init();
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
