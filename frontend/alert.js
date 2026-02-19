// Alert Component
// Reusable alert component for showing success/error/info messages

class AlertManager {
    constructor() {
        this.container = null;
        this.alertCount = 0;
        this.init();
    }

    init() {
        // Create alert container if it doesn't exist
        if (!document.querySelector('.alert-container')) {
            this.container = document.createElement('div');
            this.container.className = 'alert-container';
            this.container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 400px;
            `;
            document.body.appendChild(this.container);
        } else {
            this.container = document.querySelector('.alert-container');
        }
    }

    showAlert(message, type = 'info', duration = 5000) {
        const alertId = `alert-${Date.now()}-${this.alertCount++}`;
        const alertElement = document.createElement('div');
        
        alertElement.id = alertId;
        alertElement.className = `alert alert-${type}`;
        alertElement.innerHTML = `
            <div class="alert-content">
                <span class="alert-message">${this.escapeHtml(message)}</span>
                <button class="alert-close" aria-label="Close alert">×</button>
            </div>
        `;

        // Add to container
        this.container.appendChild(alertElement);

        // Add close functionality
        const closeButton = alertElement.querySelector('.alert-close');
        closeButton.addEventListener('click', () => {
            this.removeAlert(alertId);
        });

        // Auto-dismiss if duration is provided
        if (duration > 0) {
            setTimeout(() => {
                this.removeAlert(alertId);
            }, duration);
        }

        return alertId;
    }

    removeAlert(alertId) {
        const alertElement = document.getElementById(alertId);
        if (alertElement) {
            alertElement.style.opacity = '0';
            alertElement.style.transform = 'translateX(100%)';
            alertElement.style.transition = 'opacity 0.3s, transform 0.3s';
            
            setTimeout(() => {
                if (alertElement.parentNode) {
                    alertElement.parentNode.removeChild(alertElement);
                }
            }, 300);
        }
    }

    clearAllAlerts() {
        const alerts = this.container.querySelectorAll('.alert');
        alerts.forEach(alert => {
            this.removeAlert(alert.id);
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Create global instance
const alertManager = new AlertManager();

// Expose to window
window.showAlert = function(message, type = 'info', duration = 5000) {
    return alertManager.showAlert(message, type, duration);
};

window.removeAlert = function(alertId) {
    return alertManager.removeAlert(alertId);
};

window.clearAllAlerts = function() {
    return alertManager.clearAllAlerts();
};