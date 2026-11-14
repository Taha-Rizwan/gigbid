import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuthService } from './auth.service';
import { TenantGuard } from './tenant.guard';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Connection } from 'typeorm';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: async (cfg: ConfigService) => ({
        type: 'postgres',
        host: cfg.get<string>('DB_HOST'),
        port: cfg.get<number>('DB_PORT') || 5432,
        username: cfg.get<string>('DB_USER'),
        password: cfg.get<string>('DB_PASSWORD'),
        database: cfg.get<string>('DB_NAME'),
        entities: [],
        synchronize: false,
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [AuthService, TenantGuard],
})
export class AppModule {
  // Ensure the RLS session variable is cleared on each new DB connection
  constructor(private connection: Connection) {
    this.connection.driver.afterConnect(() => {
      return this.connection.query(`SELECT set_config('app.current_tenant', '', true)`);
    });
  }
}
