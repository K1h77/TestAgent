const request = require('supertest');
const app = require('../server');

describe('GET /api/users - Pagination', () => {
  test('should return first page with default page size of 10', async () => {
    const response = await request(app).get('/api/users');
    
    expect(response.status).toBe(200);
    expect(response.body).toHaveProperty('users');
    expect(response.body).toHaveProperty('total');
    expect(response.body.users).toHaveLength(10);
    expect(response.body.page).toBe(1);
    expect(response.body.pageSize).toBe(10);
    expect(response.body.users[0].id).toBe(1);
    expect(response.body.users[9].id).toBe(10);
  });
  
  test('should return correct page when page parameter is specified', async () => {
    const response = await request(app).get('/api/users?page=2');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(10);
    expect(response.body.page).toBe(2);
    expect(response.body.users[0].id).toBe(11);
    expect(response.body.users[9].id).toBe(20);
  });
  
  test('should return correct page size when pageSize parameter is specified', async () => {
    const response = await request(app).get('/api/users?pageSize=5');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(5);
    expect(response.body.pageSize).toBe(5);
    expect(response.body.users[0].id).toBe(1);
    expect(response.body.users[4].id).toBe(5);
  });
  
  test('should handle both page and pageSize parameters', async () => {
    const response = await request(app).get('/api/users?page=3&pageSize=5');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(5);
    expect(response.body.page).toBe(3);
    expect(response.body.pageSize).toBe(5);
    expect(response.body.users[0].id).toBe(11);
    expect(response.body.users[4].id).toBe(15);
  });
  
  test('should return remaining users on last page', async () => {
    const response = await request(app).get('/api/users?page=3&pageSize=10');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(5); // Only 5 users left (21-25)
    expect(response.body.page).toBe(3);
    expect(response.body.users[0].id).toBe(21);
    expect(response.body.users[4].id).toBe(25);
  });
  
  test('should return empty array for page beyond available data', async () => {
    const response = await request(app).get('/api/users?page=10');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(0);
    expect(response.body.page).toBe(10);
    expect(response.body.total).toBe(25);
  });
  
  test('should return total count and totalPages in response', async () => {
    const response = await request(app).get('/api/users?pageSize=7');
    
    expect(response.status).toBe(200);
    expect(response.body.total).toBe(25);
    expect(response.body.totalPages).toBe(4); // 25 users / 7 per page = 4 pages
  });
  
  test('should handle page=1 explicitly', async () => {
    const response = await request(app).get('/api/users?page=1&pageSize=15');
    
    expect(response.status).toBe(200);
    expect(response.body.users).toHaveLength(15);
    expect(response.body.page).toBe(1);
    expect(response.body.users[0].id).toBe(1);
    expect(response.body.users[14].id).toBe(15);
  });
});
