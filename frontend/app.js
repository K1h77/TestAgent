const API_URL = 'http://localhost:3000/api';

// Alert Component (make it globally accessible)
window.showAlert = function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer');
    
    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    
    // Add icon based on type
    let icon = '';
    if (type === 'success') {
        icon = '✓';
    } else if (type === 'error') {
        icon = '✕';
    } else if (type === 'info') {
        icon = 'ℹ';
    }
    
    alert.innerHTML = `
        <span class="alert-icon">${icon}</span>
        <span class="alert-message">${escapeHtml(message)}</span>
        <button class="alert-close" onclick="dismissAlert(this)">✕</button>
    `;
    
    // Add to container
    alertContainer.appendChild(alert);
    
    // Show alert with animation
    setTimeout(() => {
        alert.classList.add('show');
    }, 10);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        dismissAlert(alert.querySelector('.alert-close'));
    }, 5000);
}

function dismissAlert(closeButton) {
    const alert = closeButton.parentElement || closeButton;
    alert.classList.remove('show');
    
    // Remove from DOM after animation
    setTimeout(() => {
        if (alert.parentElement) {
            alert.parentElement.removeChild(alert);
        }
    }, 300);
}

// Handle login and show main UI
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const loginContainer = document.getElementById('loginContainer');
    const mainContainer = document.getElementById('mainContainer');
    
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        // Mock login - any credentials work
        loginContainer.style.display = 'none';
        mainContainer.style.display = 'block';
        loadTasks();
    });
    
    // Show login form initially
    loginContainer.style.display = 'block';
    mainContainer.style.display = 'none';
});

// Load all tasks from the API
async function loadTasks() {
    try {
        const response = await fetch(`${API_URL}/tasks`);
        const tasks = await response.json();
        displayTasks(tasks);
    } catch (error) {
        console.error('Error loading tasks:', error);
        alert('Failed to load tasks. Make sure the backend server is running on port 3000.');
    }
}

// Display tasks in the UI
function displayTasks(tasks) {
    const tasksList = document.getElementById('tasksList');
    tasksList.innerHTML = '';
    
    tasks.forEach(task => {
        const taskElement = document.createElement('div');
        taskElement.className = `task ${task.completed ? 'completed' : ''}`;
        taskElement.innerHTML = `
            <div class="task-header">
                <span class="task-title">${escapeHtml(task.title)}</span>
            </div>
            ${task.description ? `<div class="task-description">${escapeHtml(task.description)}</div>` : ''}
            <div class="task-actions">
                <button class="complete-btn" onclick="toggleTask(${task.id}, ${!task.completed})">
                    ${task.completed ? 'Undo' : 'Complete'}
                </button>
                <button class="delete-btn" onclick="deleteTask(${task.id})">Delete</button>
            </div>
        `;
        tasksList.appendChild(taskElement);
    });
}

// Add a new task
async function addTask() {
    const titleInput = document.getElementById('taskTitle');
    const descriptionInput = document.getElementById('taskDescription');
    
    const title = titleInput.value.trim();
    const description = descriptionInput.value.trim();
    
    if (!title) {
        showAlert('Please enter a task title', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/tasks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title, description })
        });
        
        if (response.ok) {
            titleInput.value = '';
            descriptionInput.value = '';
            showAlert('Task added successfully', 'success');
            loadTasks();
        } else {
            showAlert('Failed to add task', 'error');
        }
    } catch (error) {
        console.error('Error adding task:', error);
        alert('Failed to add task. Make sure the backend server is running.');
    }
}

// Toggle task completion status
async function toggleTask(id, completed) {
    try {
        const response = await fetch(`${API_URL}/tasks/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ completed })
        });
        
        if (response.ok) {
            showAlert('Task updated successfully', 'success');
            loadTasks();
        } else {
            showAlert('Failed to update task', 'error');
        }
    } catch (error) {
        console.error('Error updating task:', error);
        alert('Failed to update task. Make sure the backend server is running.');
    }
}

// Delete a task
async function deleteTask(id) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/tasks/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showAlert('Task deleted successfully', 'success');
            loadTasks();
        } else {
            showAlert('Failed to delete task', 'error');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        alert('Failed to delete task. Make sure the backend server is running.');
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Toggle profile modal visibility
function toggleProfile() {
    const profileModal = document.getElementById('profileModal');
    if (profileModal.style.display === 'none' || profileModal.style.display === '') {
        profileModal.style.display = 'flex';
    } else {
        profileModal.style.display = 'none';
    }
}
