# tenant‑guard

A lightweight multi‑tenant authentication and permission layer built for a fintech SaaS platform.  
It isolates each customer’s data at the **database level** using PostgreSQL row‑level security (RLS) and supports **single sign‑on (SSO)** with the client’s own identity provider.

## How it works
- **SSO** – validates OAuth2 / OpenID Connect ID tokens issued by the customer’s IdP.  
- **Tenant extraction** – the tenant identifier is taken from a claim (`tenant_id`) in the token.  
- **RLS enforcement** – a PostgreSQL session variable (`app.current_tenant`) is set for every request; policies reference this variable to filter rows.  
- **Guard** – a NestJS `CanActivate` guard aborts the request if the token is missing, invalid, or the tenant cannot be resolved.

## Setup
1. **Clone** the repo and `npm install`.  
2. Create a `.env` file (or set environment variables) with:
   ```text
   DB_HOST=...
   DB_PORT=5432
   DB_USER=...
   DB_PASSWORD=...
   DB_NAME=...
   OIDC_JWKS_URI=https://example-idp/.well-known/jwks.json
   OIDC_ISSUER=https://example-idp/
   ```
3. Run database migrations that create the `app.current_tenant` session variable and the RLS policies (outside of this repo).  
4. Start the service: `npm run start:dev`.

## Usage
Import the `TenantGuard` in any controller that needs tenant‑scoped access:

```ts
@UseGuards(TenantGuard)
@Get('invoices')
async getInvoices(@Req() req) {
  // `req.user` contains the decoded token and `tenantId`
  return this.invoiceService.findAllForTenant(req.user.tenantId);
}
```

The guard will automatically set the PostgreSQL session variable, so all subsequent queries made with the same DB connection are automatically filtered.

---  
*This code was created for a legal‑tech client and is intended as a reference implementation.*
