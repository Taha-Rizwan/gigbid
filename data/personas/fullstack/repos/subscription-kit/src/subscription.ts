import { PrismaClient, Subscription } from "@prisma/client";
import Stripe from "stripe";

const prisma = new PrismaClient();
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2022-11-15",
});

/**
 * Calculate the prorated amount for a plan change.
 *
 * @param currentSub - Current subscription record from Prisma.
 * @param newPriceId - Stripe price ID of the target plan.
 * @returns amount in cents to charge (positive) or credit (negative).
 */
export async function calculateProratedAmount(
  currentSub: Subscription,
  newPriceId: string
): Promise<number> {
  // Fetch the current price from Stripe to get unit_amount
  const currentPrice = await stripe.prices.retrieve(currentSub.stripePriceId);
  const newPrice = await stripe.prices.retrieve(newPriceId);

  // Determine remaining time in the current billing period
  const periodEnd = new Date(currentSub.currentPeriodEnd);
  const now = new Date();
  const secondsRemaining = Math.max(0, (periodEnd.getTime() - now.getTime()) / 1000);

  const periodSeconds = Math.max(
    1,
    (periodEnd.getTime() - new Date(currentSub.currentPeriodStart).getTime()) / 1000
  );

  // Pro‑rate based on price per second
  const currentRate = (currentPrice.unit_amount ?? 0) / periodSeconds;
  const newRate = (newPrice.unit_amount ?? 0) / periodSeconds;

  const remainingValue = currentRate * secondsRemaining;
  const newValue = newRate * secondsRemaining;

  // Positive means the customer owes money, negative means a credit
  return Math.round(newValue - remainingValue);
}

/**
 * Apply a plan change for a given customer.
 *
 * @param stripeCustomerId - Stripe customer identifier.
 * @param subscriptionId - Prisma subscription record ID.
 * @param newPriceId - Stripe price ID of the target plan.
 */
export async function handleSubscriptionChange(
  stripeCustomerId: string,
  subscriptionId: string,
  newPriceId: string
): Promise<void> {
  const sub = await prisma.subscription.findUniqueOrThrow({
    where: { id: subscriptionId },
  });

  const proratedAmount = await calculateProratedAmount(sub, newPriceId);

  // Create an invoice item for the prorated charge/credit
  if (proratedAmount !== 0) {
    await stripe.invoiceItems.create({
      customer: stripeCustomerId,
      amount: Math.abs(proratedAmount),
      currency: "usd",
      description: "Prorated plan change",
    });
  }

  // Update the subscription to the new price
  await stripe.subscriptions.update(sub.stripeSubscriptionId, {
    cancel_at_period_end: false,
    items: [{ price: newPriceId }],
    // If we added a credit, we need to apply it as a negative invoice item;
    // Stripe will automatically offset the next invoice.
  });

  // Persist the new price reference
  await prisma.subscription.update({
    where: { id: subscriptionId },
    data: { stripePriceId: newPriceId },
  });
}
