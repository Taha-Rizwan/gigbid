# subscription-kit

A lightweight Node library for handling subscription upgrades and downgrades with pro‑rated billing in a B2B SaaS product.

## What it does
- Calculates pro‑rated amounts when a customer changes plan mid‑cycle.  
- Creates a Stripe invoice item and updates the subscription accordingly.  
- Processes Stripe webhook events idempotently so each payment event runs only once, even if Stripe retries delivery.

## Setup
1. **Clone** the repo and install dependencies.  
   ```bash
   npm install
   ```
2. **Environment variables** (create a `.env` file at the project root):
   ```
   DATABASE_URL=postgresql://user:pass@localhost:5432/db
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
3. Run Prisma migrations (if you haven’t already):
   ```bash
   npx prisma migrate deploy
   ```

## Usage
```ts
import { handleSubscriptionChange } from "./src/subscription";
import { stripeWebhookHandler } from "./src/webhook";

// In your Next.js API route:
export default async function handler(req, res) {
  if (req.method === "POST") {
    await stripeWebhookHandler(req, res);
  } else {
    res.status(405).end();
  }
}
```

The library is deliberately small – just enough to plug into a Next.js API route and let your existing Prisma models do the heavy lifting.
