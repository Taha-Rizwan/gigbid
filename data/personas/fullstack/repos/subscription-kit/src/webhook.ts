import { NextApiRequest, NextApiResponse } from "next";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2022-11-15",
});
const endpointSecret = process.env.STRIPE_WEBHOOK_SECRET!;

/**
 * Verify Stripe signature and parse the event.
 */
function constructEvent(req: NextApiRequest): Stripe.Event {
  const sig = req.headers["stripe-signature"] as string;
  const buf = (req as any).rawBody; // Next.js can provide rawBody via middleware
  return stripe.webhooks.constructEvent(buf, sig, endpointSecret);
}

/**
 * Idempotent webhook handler – stores processed event IDs in Prisma.
 */
export async function stripeWebhookHandler(
  req: NextApiRequest,
  res: NextApiResponse
): Promise<void> {
  let event: Stripe.Event;

  try {
    event = constructEvent(req);
  } catch (err) {
    console.error("⚠️ Webhook signature verification failed.", err);
    res.status(400).send(`Webhook Error: ${err.message}`);
    return;
  }

  // Simple idempotency check
  const existing = await prisma.processedEvent.findUnique({
    where: { id: event.id },
  });
  if (existing) {
    // Already processed – acknowledge quickly
    res.json({ received: true });
    return;
  }

  // Process relevant events
  switch (event.type) {
    case "invoice.payment_succeeded":
      // In a real app you might update subscription status, send email, etc.
      console.log(`✅ Payment succeeded for ${event.data.object["id"]}`);
      break;
    case "invoice.payment_failed":
      console.log(`❌ Payment failed for ${event.data.object["id"]}`);
      // Custom logic like notifying finance could go here
      break;
    default:
      console.log(`Unhandled event type ${event.type}`);
  }

  // Record the event as processed
  await prisma.processedEvent.create({
    data: { id: event.id, type: event.type, receivedAt: new Date() },
  });

  res.json({ received: true });
}
