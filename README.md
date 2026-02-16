# TestAgent - Task Manager App

Testing autonomous ticket completion with a simple task management application.

## Overview

This is a simple Task Manager application with a backend API and frontend UI. It's designed as a test bed for autonomous agents to add features and functionality.

## Structure

- `backend/` - Node.js/Express API server
- `frontend/` - HTML/CSS/JavaScript client

## Features

- Create tasks with title and description
- View all tasks
- Mark tasks as complete/incomplete
- Delete tasks
- In-memory storage (resets on server restart)

## Getting Started

### Prerequisites

- Node.js (v14 or higher)

### Running the Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the server:
   ```bash
   npm start
   ```

The backend API will be running at `http://localhost:3000`

### Running the Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Open `index.html` in your web browser, or use a simple HTTP server:
   ```bash
   # Using Python 3
   python3 -m http.server 8080
   
   # Or using Node.js http-server (install globally: npm install -g http-server)
   http-server -p 8080
   ```

The frontend will be accessible at `http://localhost:8080`

## API Endpoints

- `GET /` - Health check
- `GET /api/tasks` - Get all tasks
- `GET /api/tasks/:id` - Get a specific task
- `POST /api/tasks` - Create a new task
- `PUT /api/tasks/:id` - Update a task
- `DELETE /api/tasks/:id` - Delete a task

## Testing Agent Features

This app is intentionally simple so agents can easily add features like:
- Persistence (database)
- User authentication
- Task categories/tags
- Due dates
- Priority levels
- Search and filtering
- And much more!
