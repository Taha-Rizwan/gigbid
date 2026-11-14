import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthService } from './auth.service';
import { Request } from 'express';
import { Connection } from 'typeorm';

/**
 * TenantGuard extracts the tenant ID from a validated ID token,
 * sets the PostgreSQL session variable, and attaches the user info
 * to the request object.
 */
@Injectable()
export class TenantGuard implements CanActivate {
  constructor(
    private readonly authService: AuthService,
    private readonly dbConnection: Connection,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request: Request = context.switchToHttp().getRequest();

    const authHeader = request.headers['authorization'];
    if (!authHeader) {
      throw new UnauthorizedException('Missing Authorization header');
    }

    const token = authHeader.replace('Bearer ', '');
    const payload = await this.authService.validateToken(token);

    const tenantId = payload['tenant_id'];
    if (!tenantId) {
      throw new UnauthorizedException('Tenant claim missing in token');
    }

    // Attach user info for downstream handlers
    (request as any).user = {
      sub: payload.sub,
      email: payload.email,
      tenantId,
    };

    // Set PostgreSQL session variable for RLS
    await this.dbConnection.query(
      `SELECT set_config('app.current_tenant', $1, true)`,
      [tenantId],
    );

    return true;
  }
}
