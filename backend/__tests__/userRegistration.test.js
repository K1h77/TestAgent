const request = require('supertest');
const express = require('express');

// We'll need to refactor server.js to export the app for testing
// For now, we'll create a test setup that mimics the server structure
describe('POST /api/register - Password Validation', () => {
  let app;

  beforeEach(() => {
    // We'll need to import the actual app from server.js
    // For now, this will fail until we implement the endpoint
    app = require('../server.js');
  });

  describe('Password length validation', () => {
    test('should reject password with less than 12 characters', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'Short1@'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('at least 12 characters');
    });

    test('should accept password with exactly 12 characters that meets all criteria', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'Valid1Pass@!'
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id');
      expect(response.body).toHaveProperty('username', 'testuser');
      expect(response.body).not.toHaveProperty('password');
    });

    test('should accept password with more than 12 characters that meets all criteria', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser2',
          email: 'test2@example.com',
          password: 'VerySecure1Password@!'
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id');
    });
  });

  describe('Password character requirements', () => {
    test('should reject password without uppercase letter', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'nouppercase1@'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('uppercase');
    });

    test('should reject password without lowercase letter', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'NOLOWERCASE1@'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('lowercase');
    });

    test('should reject password without number', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'NoNumberHere@'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('number');
    });

    test('should reject password without symbol', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'NoSymbolHere1'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('symbol');
    });

    test('should reject password missing multiple requirements', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com',
          password: 'onlylowercase'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toBeTruthy();
      // Should mention it's missing requirements
      expect(response.body.error.length).toBeGreaterThan(0);
    });
  });

  describe('Valid password scenarios', () => {
    test('should accept password with all requirements met', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'validuser',
          email: 'valid@example.com',
          password: 'SecurePass123!'
        });

      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('id');
      expect(response.body).toHaveProperty('username', 'validuser');
      expect(response.body).toHaveProperty('email', 'valid@example.com');
      expect(response.body).not.toHaveProperty('password');
    });

    test('should accept password with various symbols', async () => {
      const passwords = [
        'ValidPass123!',
        'ValidPass123@',
        'ValidPass123#',
        'ValidPass123$',
        'ValidPass123%',
        'ValidPass123^',
        'ValidPass123&',
        'ValidPass123*'
      ];

      for (let i = 0; i < passwords.length; i++) {
        const response = await request(app)
          .post('/api/register')
          .send({
            username: `user${i}`,
            email: `user${i}@example.com`,
            password: passwords[i]
          });

        expect(response.status).toBe(201);
      }
    });
  });

  describe('Missing fields validation', () => {
    test('should reject registration without password', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          email: 'test@example.com'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toBeTruthy();
    });

    test('should reject registration without username', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          email: 'test@example.com',
          password: 'ValidPass123!'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toBeTruthy();
    });

    test('should reject registration without email', async () => {
      const response = await request(app)
        .post('/api/register')
        .send({
          username: 'testuser',
          password: 'ValidPass123!'
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toBeTruthy();
    });
  });
});
