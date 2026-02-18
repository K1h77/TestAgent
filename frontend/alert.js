/**
 * Reusable Alert Component
 * Supports different statuses: success, error, info
 * Includes close/dismiss functionality
 * Auto-dismiss after timeout (optional)
 */

class AlertComponent {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    // Create alert container if it doesn't exist
    if (!document.getElementById('alert-container')) {
      this.container = document.createElement('div');
      this.container.id = 'alert-container';
      this.container.className = 'alert-container';
      document.body.appendChild(this.container);
      
      // Add CSS styles if not already present
      this.addStyles();
    } else {
      this.container = document.getElementById('alert-container');
    }
  }

  addStyles() {
    // Only add styles once
    if (document.getElementById('alert-styles')) return;

    const style = document.createElement('style');
    style.id = 'alert-styles';
    style.textContent = `
      .alert-container {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 400px;
      }

      .alert {
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        justify-content: space-between;
        animation: slideIn 0.3s ease-out;
        transition: opacity 0.3s, transform 0.3s;
      }

      .alert.hiding {
        opacity: 0;
        transform: translateX(100%);
      }

      .alert.success {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        border-left: 4px solid #0d7a6e;
      }

      .alert.error {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        color: white;
        border-left: 4px solid #c62828;
      }

      .alert.info {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-left: 4px solid #5d6bc0;
      }

      .alert-content {
        flex: 1;
        margin-right: 15px;
        font-size: 14px;
        line-height: 1.4;
      }

      .alert-close {
        background: rgba(255, 255, 255, 0.2);
        border: none;
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 16px;
        padding: 0;
        transition: background 0.2s;
      }

      .alert-close:hover {
        background: rgba(255, 255, 255, 0.3);
      }

      @keyframes slideIn {
        from {
          opacity: 0;
          transform: translateX(100%);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }
    `;
    document.head.appendChild(style);
  }

  show(message, type = 'info', timeout = 5000) {
    // Validate type
    const validTypes =['success', 'error', 'info'];
    if (!validTypes.includes(type)) {
      type = 'info';
    }

    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert ${type}`;
    
    // Create content
    const content = document.createElement('div');
    content.className = 'alert-content';
    content.textContent = message;
    
    // Create close button
    const closeButton = document.createElement('button');
    closeButton.className = 'alert-close';
    closeButton.innerHTML = '×';
    closeButton.setAttribute('aria-label', 'Close alert');
    
    // Add elements
    alert.appendChild(content);
    alert.appendChild(closeButton);
    this.container.appendChild(alert);
    
    // Set up close functionality
    const dismiss = () => {
      alert.classList.add('hiding');
      setTimeout(() => {
        if (alert.parentNode) {
          alert.parentNode.removeChild(alert);
        }
      }, 300);
    };
    
    closeButton.addEventListener('click', dismiss);
    
    // Auto-dismiss after timeout if specified
    if (timeout > 0) {
      setTimeout(dismiss, timeout);
    }
    
    return {
      dismiss,
      element: alert
    };
  }

  success(message, timeout = 5000) {
    return this.show(message, 'success', timeout);
  }

  error(message, timeout = 5000) {
    return this.show(message, 'error', timeout);
  }

  info(message, timeout = 5000) {
    return this.show(message, 'info', timeout);
  }

  clearAll() {
    while (this.container.firstChild) {
      this.container.removeChild(this.container.firstChild);
    }
  }
}

// Create global instance
const alertComponent = new AlertComponent();

// Expose to window for easy access
window.alertComponent = alertComponent;
window.showAlert = (message, type = 'info', timeout = 5000) => {
  return alertComponent.show(message, type, timeout);
};

// Export for module usage (if using modules)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = alertComponent;
}