import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ConfigService } from '@nestjs/config';
import { Logger } from '@nestjs/common';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const config = app.get(ConfigService);
  const port = config.get<number>('PORT') || 3000;

  // Global guard registration
  const { TenantGuard } = await import('./tenant.guard');
  app.useGlobalGuards(new TenantGuard());

  await app.listen(port);
  Logger.log(`Tenant‑guard service listening on ${port}`);
}
bootstrap();
