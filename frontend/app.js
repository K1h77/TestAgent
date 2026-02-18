const API_URL = 'http://localhost:3000/api';

// Loading indicator helper functions
function showLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
}

function hideLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
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
    showLoading();
    try {
        const response = await fetch(`${API_URL}/tasks`);
        const tasks = await response.json();
        displayTasks(tasks);
    } catch (error) {
        console.error('Error loading tasks:', error);
        alert('Failed to load tasks. Make sure the backend server is running on port 3000.');
    } finally {
        hideLoading();
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
        alert('Please enter a task title');
        return;
    }
    
    showLoading();
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
            loadTasks();
        } else {
            hideLoading();
            alert('Failed to add task');
        }
    } catch (error) {
        hideLoading();
        console.error('Error adding task:', error);
        alert('Failed to add task. Make sure the backend server is running.');
    }
}

// Toggle task completion status
async function toggleTask(id, completed) {
    showLoading();
    try {
        const response = await fetch(`${API_URL}/tasks/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ completed })
        });
        
        if (response.ok) {
            loadTasks();
        } else {
            hideLoading();
            alert('Failed to update task');
        }
    } catch (error) {
        hideLoading();
        console.error('Error updating task:', error);
        alert('Failed to update task. Make sure the backend server is running.');
    }
}

// Delete a task
async function deleteTask(id) {
    if (!confirm('Are you sure you want to delete this task?')) {
        return;
    }
    
    showLoading();
    try {
        const response = await fetch(`${API_URL}/tasks/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadTasks();
        } else {
            hideLoading();
            alert('Failed to delete task');
        }
    } catch (error) {
        hideLoading();
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
