import { Request, Response, NextFunction } from 'express';
import { ZodSchema, ZodError } from 'zod';

/**
 * Returns an Express middleware that validates req.body against a Zod schema.
 * If validation fails, it forwards a 400 error with details.
 *
 * @param schema Zod schema to validate against
 */
export function validate(schema: ZodSchema<any>) {
  return (req: Request, _res: Response, next: NextFunction) => {
    try {
      req.body = schema.parse(req.body);
      next();
    } catch (e) {
      if (e instanceof ZodError) {
        const err: any = new Error('Invalid request payload');
        err.status = 400;
        err.details = e.errors;
        next(err);
      } else {
        next(e);
      }
    }
  };
}
