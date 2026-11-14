import { PrismaClient } from '@prisma/client';

/**
 * Prisma client singleton.
 * Reads DATABASE_URL from environment; throws if missing.
 */
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error('DATABASE_URL environment variable is required');
}

export const prisma = new PrismaClient({
  datasources: { db: { url: databaseUrl } },
});
