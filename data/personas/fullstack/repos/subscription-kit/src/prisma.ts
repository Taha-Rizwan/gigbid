import { PrismaClient } from "@prisma/client";

/**
 * Singleton Prisma client to avoid exhausting connections in serverless environments.
 */
const prisma = new PrismaClient();

export default prisma;
