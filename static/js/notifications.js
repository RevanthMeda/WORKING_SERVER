
class NotificationSystem {
    constructor() {
        this.pollInterval = 30000; // Poll every 30 seconds
        this.isPolling = false;
        this.notificationContainer = null;
        this.init();
    }

    init() {
        this.createNotificationElements();
        this.loadInitialNotifications();
        this.startPolling();
        this.bindEvents();
    }

    createNotificationElements() {
        // Create notification bell icon if it doesn't exist
        const nav = document.querySelector('.nav-links') || document.querySelector('nav');
        if (nav && !document.getElementById('notification-bell')) {
            const bellHtml = `
                <div class="notification-wrapper">
                    <button id="notification-bell" class="notification-bell" title="Notifications">
                        <i class="fas fa-bell"></i>
                        <span id="notification-badge" class="notification-badge" style="display: none;">0</span>
                    </button>
                    <div id="notification-dropdown" class="notification-dropdown" style="display: none;">
                        <div class="notification-header">
                            <h3>Notifications</h3>
                            <button id="mark-all-read" class="mark-all-read">Mark all read</button>
                        </div>
                        <div id="notification-list" class="notification-list">
                            <div class="loading">Loading notifications...</div>
                        </div>
                        <div class="notification-footer">
                            <a href="/notifications" class="view-all">View All Notifications</a>
                        </div>
                    </div>
                </div>
            `;
            nav.insertAdjacentHTML('beforeend', bellHtml);
        }
    }

    bindEvents() {
        const bell = document.getElementById('notification-bell');
        const dropdown = document.getElementById('notification-dropdown');
        const markAllRead = document.getElementById('mark-all-read');

        if (bell) {
            bell.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        if (markAllRead) {
            markAllRead.addEventListener('click', () => {
                this.markAllAsRead();
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (dropdown && !dropdown.contains(e.target) && !bell.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    }

    async loadInitialNotifications() {
        try {
            const response = await fetch('/notifications/api/notifications');
            const data = await response.json();
            
            if (data.success) {
                this.updateNotificationBadge(data.unread_count);
                this.renderNotifications(data.notifications);
            }
        } catch (error) {
            console.error('Error loading notifications:', error);
        }
    }

    async startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;

        const poll = async () => {
            try {
                const response = await fetch('/notifications/api/notifications/unread-count');
                const data = await response.json();
                
                if (data.success) {
                    this.updateNotificationBadge(data.count);
                }
            } catch (error) {
                console.error('Error polling notifications:', error);
            }
            
            if (this.isPolling) {
                setTimeout(poll, this.pollInterval);
            }
        };

        poll();
    }

    stopPolling() {
        this.isPolling = false;
    }

    updateNotificationBadge(count) {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    async toggleDropdown() {
        const dropdown = document.getElementById('notification-dropdown');
        if (!dropdown) return;

        if (dropdown.style.display === 'none' || !dropdown.style.display) {
            // Load fresh notifications when opening
            await this.loadNotifications();
            dropdown.style.display = 'block';
        } else {
            dropdown.style.display = 'none';
        }
    }

    async loadNotifications() {
        const list = document.getElementById('notification-list');
        if (!list) return;

        list.innerHTML = '<div class="loading">Loading notifications...</div>';

        try {
            const response = await fetch('/notifications/api/notifications');
            const data = await response.json();
            
            if (data.success) {
                this.renderNotifications(data.notifications);
                this.updateNotificationBadge(data.unread_count);
            } else {
                list.innerHTML = '<div class="error">Error loading notifications</div>';
            }
        } catch (error) {
            console.error('Error loading notifications:', error);
            list.innerHTML = '<div class="error">Error loading notifications</div>';
        }
    }

    renderNotifications(notifications) {
        const list = document.getElementById('notification-list');
        if (!list) return;

        if (notifications.length === 0) {
            list.innerHTML = '<div class="no-notifications">No notifications</div>';
            return;
        }

        const html = notifications.map(notification => {
            const timeAgo = this.getTimeAgo(new Date(notification.created_at));
            const readClass = notification.read ? 'read' : 'unread';
            const actionButton = notification.action_url ? 
                `<button class="notification-action" onclick="window.open('${notification.action_url}', '_blank')">View</button>` : '';

            return `
                <div class="notification-item ${readClass}" data-id="${notification.id}">
                    <div class="notification-content">
                        <h4>${notification.title}</h4>
                        <p>${notification.message}</p>
                        <small class="notification-time">${timeAgo}</small>
                    </div>
                    <div class="notification-actions">
                        ${actionButton}
                        ${!notification.read ? '<button class="mark-read" onclick="notificationSystem.markAsRead(' + notification.id + ')">Mark read</button>' : ''}
                    </div>
                </div>
            `;
        }).join('');

        list.innerHTML = html;
    }

    async markAsRead(notificationId) {
        try {
            const response = await fetch(`/notifications/api/notifications/${notificationId}/mark-read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
                }
            });

            const data = await response.json();
            if (data.success) {
                // Update UI
                const item = document.querySelector(`[data-id="${notificationId}"]`);
                if (item) {
                    item.classList.remove('unread');
                    item.classList.add('read');
                    const markReadBtn = item.querySelector('.mark-read');
                    if (markReadBtn) markReadBtn.remove();
                }
                
                // Refresh count
                await this.loadInitialNotifications();
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    async markAllAsRead() {
        try {
            const response = await fetch('/notifications/api/notifications/mark-all-read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || ''
                }
            });

            const data = await response.json();
            if (data.success) {
                // Refresh notifications
                await this.loadNotifications();
            }
        } catch (error) {
            console.error('Error marking all notifications as read:', error);
        }
    }

    getTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    // Public method to create notifications from other parts of the app
    static showToast(title, message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `notification-toast notification-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <h4>${title}</h4>
                <p>${message}</p>
            </div>
            <button class="toast-close">&times;</button>
        `;

        document.body.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);

        // Close button
        toast.querySelector('.toast-close').addEventListener('click', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }
}

// Initialize notification system when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.notificationSystem = new NotificationSystem();
});

// Expose toast method globally
window.showNotificationToast = NotificationSystem.showToast;
