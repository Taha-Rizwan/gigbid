/**
 * Minimal type definitions for the parts of the Stripe event we use.
 * This keeps the bundle small without pulling in the full @types/stripe package.
 */
export interface StripeInvoiceObject {
  id: string;
  amount_paid: number;
  // Add more fields as needed
}
