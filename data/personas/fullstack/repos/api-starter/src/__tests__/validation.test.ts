import { describe, expect, test } from 'vitest';
import request from 'supertest';
import { app } from '../server';
import { z } from 'zod';

describe('validation middleware', () => {
  const schema = z.object({ foo: z.string() });

  test('passes valid payload', async () => {
    const res = await request(app)
      .post('/api/test')
      .send({ foo: 'bar' })
      .set('Accept', 'application/json');
    expect(res.status).not.toBe(400);
  });

  test('rejects invalid payload', async () => {
    const res = await request(app)
      .post('/api/test')
      .send({ foo: 123 })
      .set('Accept', 'application/json');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid request payload');
  });
});
