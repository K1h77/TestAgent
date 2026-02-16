#!/bin/bash

# Simple test script to verify the app setup

echo "Testing Task Manager App Setup..."
echo "=================================="
echo ""

# Test backend
echo "1. Testing Backend API..."
BACKEND_RESPONSE=$(curl -s http://localhost:3000/)
if [[ $BACKEND_RESPONSE == *"Task Manager API"* ]]; then
    echo "✅ Backend is running on port 3000"
else
    echo "❌ Backend is not responding. Make sure to run 'npm start' in backend/"
    exit 1
fi

# Test API endpoints
echo ""
echo "2. Testing API Endpoints..."
TASKS_RESPONSE=$(curl -s http://localhost:3000/api/tasks)
if [[ $TASKS_RESPONSE == *"id"* ]]; then
    echo "✅ GET /api/tasks is working"
else
    echo "❌ API endpoints not responding correctly"
    exit 1
fi

# Test frontend
echo ""
echo "3. Testing Frontend..."
FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
if [ "$FRONTEND_RESPONSE" == "200" ]; then
    echo "✅ Frontend is accessible on port 8080"
else
    echo "❌ Frontend is not responding. Make sure to run a web server in frontend/"
    exit 1
fi

echo ""
echo "=================================="
echo "✅ All tests passed!"
echo ""
echo "Access the app at: http://localhost:8080"
