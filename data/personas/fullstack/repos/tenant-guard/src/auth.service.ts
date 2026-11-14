import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as jwt from 'jsonwebtoken';
import * as jwksClient from 'jwks-rsa';
import { JwksClient, SigningKey } from 'jwks-rsa';

/**
 * AuthService validates an OpenID Connect ID token and extracts the tenant ID.
 */
@Injectable()
export class AuthService {
  private jwks: JwksClient;

  constructor(private config: ConfigService) {
    const jwksUri = this.config.get<string>('OIDC_JWKS_URI');
    if (!jwksUri) {
      throw new Error('OIDC_JWKS_URI not configured');
    }
    this.jwks = jwksClient({ jwksUri });
  }

  /**
   * Verify token signature using the JWKS endpoint.
   */
  private async getSigningKey(kid: string): Promise<SigningKey> {
    return new Promise((resolve, reject) => {
      this.jwks.getSigningKey(kid, (err, key) => {
        if (err) return reject(err);
        resolve(key);
      });
    });
  }

  /**
   * Validate the JWT and return the decoded payload.
   */
  async validateToken(token: string): Promise<any> {
    const decoded = jwt.decode(token, { complete: true });
    if (!decoded || typeof decoded === 'string') {
      throw new UnauthorizedException('Invalid token');
    }

    const kid = decoded.header.kid;
    const signingKey = await this.getSigningKey(kid);
    const publicKey = signingKey.getPublicKey();

    try {
      const payload = jwt.verify(token, publicKey, {
        algorithms: ['RS256'],
        issuer: this.config.get<string>('OIDC_ISSUER'),
      });
      return payload;
    } catch (e) {
      throw new UnauthorizedException('Token verification failed');
    }
  }
}
