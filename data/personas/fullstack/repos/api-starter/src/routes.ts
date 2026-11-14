import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { validate } from './validation';
import { prisma } from './db';

export const router = Router();

/**
 * Example: Create a new "Project" record.
 * Expected body: { name: string, clientId: number }
 */
const createProjectSchema = z.object({
  name: z.string().min(1),
  clientId: z.number().int().positive(),
});

router.post(
  '/projects',
  validate(createProjectSchema),
  async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { name, clientId } = req.body;
      const project = await prisma.project.create({
        data: { name, clientId },
      });
      res.status(201).json(project);
    } catch (e) {
      next(e);
    }
  }
);
