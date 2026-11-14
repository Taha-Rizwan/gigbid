import { Test, TestingModule } from '@nestjs/testing';
import { TenantGuard } from '../src/tenant.guard';
import { AuthService } from '../src/auth.service';
import { Connection } from 'typeorm';
import { UnauthorizedException } from '@nestjs/common';
import { ExecutionContext } from '@nestjs/common/interfaces';

describe('TenantGuard', () => {
  let guard: TenantGuard;
  let authService: AuthService;
  let dbConnection: Connection;

  const mockPayload = {
    sub: 'user-123',
    email: 'user@example.com',
    tenant_id: 'tenant-42',
  };

  beforeEach(async () => {
    const authMock = {
      validateToken: jest.fn().mockResolvedValue(mockPayload),
    };
    const dbMock = {
      query: jest.fn().mockResolvedValue(undefined),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TenantGuard,
        { provide: AuthService, useValue: authMock },
        { provide: Connection, useValue: dbMock },
      ],
    }).compile();

    guard = module.get<TenantGuard>(TenantGuard);
    authService = module.get<AuthService>(AuthService);
    dbConnection = module.get<Connection>(Connection);
  });

  it('should allow request with valid token and set tenant', async () => {
    const ctx = {
      switchToHttp: () => ({
        getRequest: () => ({
          headers: { authorization: 'Bearer valid-token' },
        }),
      }),
    } as ExecutionContext;

    const result = await guard.canActivate(ctx);
    expect(result).toBe(true);
    expect(authService.validateToken).toHaveBeenCalledWith('valid-token');
    expect(dbConnection.query).toHaveBeenCalledWith(
      `SELECT set_config('app.current_tenant', $1, true)`,
      ['tenant-42'],
    );
  });

  it('should reject request without Authorization header', async () => {
    const ctx = {
      switchToHttp: () => ({
        getRequest: () => ({
          headers: {},
        }),
      }),
    } as ExecutionContext;

    await expect(guard.canActivate(ctx)).rejects.toThrow(UnauthorizedException);
  });
});
