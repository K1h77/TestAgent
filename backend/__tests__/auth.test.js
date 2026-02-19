const request = require('supertest');
const app = require('../server');

describe('Authentication API', () => {
  describe('POST /api/login', () => {
    test('should return success with valid credentials', async () => {
      const response = await request(app)
        .post('/api/login')
        .send({
          username: 'testuser',
          password: 'testpass'
        });
      
      expect(response.statusCode).toBe(200);
      expect(response.body).toHaveProperty('success', true);
      expect(response.body).toHaveProperty('message', 'Login successful');
    });

    test('should return error with invalid username', async () => {
      const response = await request(app)
        .post('/api/login')
        .send({
          username: 'wronguser',
          password: 'testpass'
        });
      
      expect(response.statusCode).toBe(401);
      expect(response.body).toHaveProperty('success', false);
      expect(response.body).toHaveProperty('message', 'Invalid credentials');
    });

    test('should return error with invalid password', async () => {
      const response = await request(app)
        .post('/api/login')
        .send({
          username: 'testuser',
          password: 'wrongpass'
        });
      
      expect(response.statusCode).toBe(401);
      expect(response.body).toHaveProperty('success', false);
      expect(response.body).toHaveProperty('message', 'Invalid credentials');
    });

    test('should return error with missing username', async () => {
      const response = await request(app)
        .post('/api/login')
        .send({
          password: 'testpass'
        });
      
      expect(response.statusCode).toBe(400);
      expect(response.body).toHaveProperty('success', false);
      expect(response.body).toHaveProperty('message', 'Username and password are required');
    });

    test('should return error with missing password', async () => {
      const response = await request(app)
        .post('/api/login')
        .send({
          username: 'testuser'
        });
      
      expect(response.statusCode).toBe(400);
      expect(response.body).toHaveProperty('success', false);
      expect(response.body).toHaveProperty('message', 'Username and password are required');
    });
  });
});