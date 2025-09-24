/**
 * CSRF Token Manager - Automatically handles CSRF token refresh
 * Prevents "CSRF token expired" errors
 */
class CSRFManager {
    constructor() {
        this.refreshInterval = 300000; // 5 minutes
        this.maxRetries = 3;
        this.retryCount = 0;
        
        this.init();
    }
    
    init() {
        console.log('🔐 CSRF Manager initialized');
        
        // Start periodic refresh
        this.startPeriodicRefresh();
        
        // Handle form submissions
        this.interceptFormSubmissions();
        
        // Handle AJAX calls
        this.setupAjaxInterceptor();
        
        // Refresh token when page becomes visible (handle tab switching)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.refreshToken();
            }
        });
    }
    
    async refreshToken() {
        try {
            console.log('🔄 Refreshing CSRF token...');
            
            const response = await fetch('/health', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Look for CSRF token in response
                if (data.csrf_token) {
                    this.updateAllTokens(data.csrf_token);
                    console.log('✅ CSRF token refreshed successfully');
                    this.retryCount = 0;
                } else {
                    // Generate new token via meta tag method
                    this.generateNewToken();
                }
            } else {
                throw new Error('Failed to refresh token');
            }
            
        } catch (error) {
            console.error('❌ Failed to refresh CSRF token:', error);
            this.retryCount++;
            
            if (this.retryCount < this.maxRetries) {
                setTimeout(() => this.refreshToken(), 5000); // Retry in 5 seconds
            } else {
                console.warn('⚠️ Max retries reached. User may see CSRF errors.');
            }
        }
    }
    
    generateNewToken() {
        // Force a new token by making a simple request
        fetch(window.location.href, {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const metaToken = doc.querySelector('meta[name="csrf-token"]');
            
            if (metaToken) {
                const newToken = metaToken.getAttribute('content');
                this.updateAllTokens(newToken);
                console.log('✅ New CSRF token generated');
            }
        });
    }
    
    updateAllTokens(newToken) {
        // Update all CSRF token inputs
        const tokenInputs = document.querySelectorAll('input[name="csrf_token"]');
        tokenInputs.forEach(input => {
            input.value = newToken;
        });
        
        // Update meta tag
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            metaToken.setAttribute('content', newToken);
        }
        
        // Store in global variable for AJAX calls
        window.csrfToken = newToken;
        
        console.log(`🔄 Updated ${tokenInputs.length} CSRF tokens`);
    }
    
    startPeriodicRefresh() {
        setInterval(() => {
            this.refreshToken();
        }, this.refreshInterval);
        
        console.log(`⏰ CSRF token will refresh every ${this.refreshInterval/1000} seconds`);
    }
    
    interceptFormSubmissions() {
        document.addEventListener('submit', (e) => {
            const form = e.target;
            const csrfInput = form.querySelector('input[name="csrf_token"]');
            
            if (csrfInput && !csrfInput.value) {
                e.preventDefault();
                console.warn('⚠️ Form submission blocked: Missing CSRF token');
                this.refreshToken().then(() => {
                    form.submit();
                });
            }
        });
    }
    
    setupAjaxInterceptor() {
        // Override fetch to automatically include CSRF tokens
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (options.method && options.method.toUpperCase() !== 'GET') {
                options.headers = options.headers || {};
                
                if (!options.headers['X-CSRFToken']) {
                    const token = window.csrfToken || 
                                document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                                document.querySelector('input[name="csrf_token"]')?.value;
                    
                    if (token) {
                        options.headers['X-CSRFToken'] = token;
                    }
                }
            }
            
            return originalFetch.call(this, url, options);
        };
    }
}

// Initialize CSRF Manager when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.csrfManager = new CSRFManager();
});

// Also handle cases where DOMContentLoaded already fired
if (document.readyState === 'loading') {
    // Document still loading, wait for DOMContentLoaded
} else {
    // Document already loaded
    window.csrfManager = new CSRFManager();
}