import express, { Request, Response, NextFunction } from 'express';
import { json } from 'body-parser';
import { prisma } from './db';
import { validate } from './validation';
import { router } from './routes';

/**
 * Global error handler – formats thrown errors as JSON.
 */
function errorHandler(err: any, _req: Request, res: Response, _next: NextFunction) {
  console.error(err);
  const status = err.status ?? 500;
  const message = err.message ?? 'Internal Server Error';
  res.status(status).json({ error: message });
}

const app = express();
app.use(json());

// Example health check
app.get('/health', (_req, res) => res.json({ status: 'ok' }));

// Mount API routes
app.use('/api', router);

// Catch‑all error handling
app.use(errorHandler);

const PORT = process.env.PORT ?? 3000;
app.listen(PORT, () => {
  console.log(`🚀 API listening on http://localhost:${PORT}`);
});

export { app };
