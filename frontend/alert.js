/**
 * Alert Component - Reusable alert component for showing success/error/info messages
 * Supports different statuses (success, error, info) with close/dismiss functionality
 */

// Alert status types
const AlertStatus = {
  SUCCESS: 'success',
  ERROR: 'error',
  INFO: 'info'
};

// Default configuration
const DEFAULT_CONFIG = {
  autoDismiss: true,
  dismissTimeout: 5000, // 5 seconds
  position: 'top-right'
};

// Alert container CSS class
const ALERT_CONTAINER_CLASS = 'alert-container';

// Alert CSS classes
const ALERT_BASE_CLASS = 'alert';
const ALERT_SUCCESS_CLASS = 'alert-success';
const ALERT_ERROR_CLASS = 'alert-error';
const ALERT_INFO_CLASS = 'alert-info';
const ALERT_CLOSE_CLASS = 'alert-close';

/**
 * Initialize alert system
 * Creates alert container if it doesn't exist
 */
function initAlertSystem() {
  // Create alert container if it doesn't exist
  if (!document.querySelector(`.${ALERT_CONTAINER_CLASS}`)) {
    const container = document.createElement('div');
    container.className = ALERT_CONTAINER_CLASS;
    document.body.appendChild(container);
  }
}

/**
 * Show an alert message
 * @param {string} message - The alert message to display
 * @param {string} status - Alert status: 'success', 'error', or 'info'
 * @param {Object} options - Alert options
 * @param {number} options.dismissTimeout - Auto-dismiss timeout in ms (0 = no auto-dismiss)
 * @param {boolean} options.autoDismiss - Whether to auto-dismiss
 */
function showAlert(message, status = AlertStatus.INFO, options = {}) {
  // Initialize alert system if not already done
  initAlertSystem();
  
  // Merge options with defaults
  const config = { ...DEFAULT_CONFIG, ...options };
  
  // Get alert container
  const container = document.querySelector(`.${ALERT_CONTAINER_CLASS}`);
  
  // Create alert element
  const alert = document.createElement('div');
  alert.className = `${ALERT_BASE_CLASS} alert-${status}`;
  
  // Set alert content
  alert.innerHTML = `
    <div class="alert-content">${escapeHtml(message)}</div>
    <button class="${ALERT_CLOSE_CLASS}" aria-label="Close alert">×</button>
  `;
  
  // Add alert to container
  container.appendChild(alert);
  
  // Add close functionality
  const closeButton = alert.querySelector(`.${ALERT_CLOSE_CLASS}`);
  closeButton.addEventListener('click', () => {
    dismissAlert(alert);
  });
  
  // Auto-dismiss if enabled
  if (config.autoDismiss && config.dismissTimeout > 0) {
    setTimeout(() => {
      dismissAlert(alert);
    }, config.dismissTimeout);
  }
  
  // Trigger animation
  setTimeout(() => {
    alert.style.opacity = '1';
    alert.style.transform = 'translateX(0)';
  }, 10);
  
  return {
    dismiss: () => dismissAlert(alert),
    element: alert
  };
}

/**
 * Dismiss/remove an alert
 * @param {HTMLElement} alert - The alert element to dismiss
 */
function dismissAlert(alert) {
  if (!alert || !alert.parentNode) return;
  
  alert.style.opacity = '0';
  alert.style.transform = 'translateX(100%)';
  
  setTimeout(() => {
    if (alert.parentNode) {
      alert.parentNode.removeChild(alert);
    }
  }, 300);
}

/**
 * Show success alert
 * @param {string} message - Success message
 * @param {Object} options - Alert options
 */
function showSuccessAlert(message, options = {}) {
  return showAlert(message, AlertStatus.SUCCESS, options);
}

/**
 * Show error alert
 * @param {string} message - Error message
 * @param {Object} options - Alert options
 */
function showErrorAlert(message, options = {}) {
  return showAlert(message, AlertStatus.ERROR, options);
}

/**
 * Show info alert
 * @param {string} message - Info message
 * @param {Object} options - Alert options
 */
function showInfoAlert(message, options = {}) {
  return showAlert(message, AlertStatus.INFO, options);
}

/**
 * Clear all alerts
 */
function clearAllAlerts() {
  const container = document.querySelector(`.${ALERT_CONTAINER_CLASS}`);
  if (container) {
    container.innerHTML = '';
  }
}

/**
 * Helper function to escape HTML
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Export functions to global scope
window.AlertSystem = {
  showAlert,
  showSuccessAlert,
  showErrorAlert,
  showInfoAlert,
  clearAllAlerts,
  AlertStatus
};

// Initialize alert system when DOM is loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAlertSystem);
} else {
  initAlertSystem();
}

// Make showAlert available globally for backward compatibility
window.showAlert = showAlert;