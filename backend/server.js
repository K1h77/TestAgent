const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve frontend static files
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// In-memory storage for tasks
let tasks = [
  { id: 1, title: 'Sample Task', description: 'This is a sample task', completed: false }
];
let nextId = 2;

// In-memory storage for users
let users = [];
for (let i = 1; i <= 25; i++) {
  users.push({
    id: i,
    name: `User ${i}`,
    email: `user${i}@example.com`
  });
}

// Routes
app.get('/', (req, res) => {
  res.json({ message: 'Task Manager API - Server is running!' });
});

// Get all tasks
app.get('/api/tasks', (req, res) => {
  res.json(tasks);
});

// Get a single task
app.get('/api/tasks/:id', (req, res) => {
  const task = tasks.find(t => t.id === parseInt(req.params.id));
  if (!task) {
    return res.status(404).json({ error: 'Task not found' });
  }
  res.json(task);
});

// Create a new task
app.post('/api/tasks', (req, res) => {
  const { title, description } = req.body;
  if (!title) {
    return res.status(400).json({ error: 'Title is required' });
  }
  
  const newTask = {
    id: nextId++,
    title,
    description: description || '',
    completed: false
  };
  
  tasks.push(newTask);
  res.status(201).json(newTask);
});

// Update a task
app.put('/api/tasks/:id', (req, res) => {
  const task = tasks.find(t => t.id === parseInt(req.params.id));
  if (!task) {
    return res.status(404).json({ error: 'Task not found' });
  }
  
  const { title, description, completed } = req.body;
  if (title !== undefined) task.title = title;
  if (description !== undefined) task.description = description;
  if (completed !== undefined) task.completed = completed;
  
  res.json(task);
});

// Delete a task
app.delete('/api/tasks/:id', (req, res) => {
  const index = tasks.findIndex(t => t.id === parseInt(req.params.id));
  if (index === -1) {
    return res.status(404).json({ error: 'Task not found' });
  }
  
  tasks.splice(index, 1);
  res.json({ message: 'Task deleted successfully' });
});

// Get users with pagination
app.get('/api/users', (req, res) => {
  // Parse query parameters with defaults
  const page = parseInt(req.query.page) || 1;
  const pageSize = parseInt(req.query.pageSize) || 10;
  
  // Calculate pagination
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  
  // Get paginated users
  const paginatedUsers = users.slice(startIndex, endIndex);
  
  // Return paginated response
  res.json({
    users: paginatedUsers,
    total: users.length,
    page: page,
    pageSize: pageSize,
    totalPages: Math.ceil(users.length / pageSize)
  });
});

// Only start the server if this file is run directly (not required for testing)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
  });
}

module.exports = app;
