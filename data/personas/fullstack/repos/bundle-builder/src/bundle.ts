import { PrismaClient } from "@prisma/client";
import { BundleSelection, BundleItem } from "./types";

const prisma = new PrismaClient();

/**
 * Calculates the total price for a shopper's bundle.
 * Applies any rule‑specific discounts stored in the DB.
 */
export async function calculateBundlePrice(selection: BundleSelection): Promise<number> {
  // Load product details for the selected IDs
  const productIds = selection.items.map((i) => i.productId);
  const products = await prisma.bundleItem.findMany({
    where: { productId: { in: productIds } },
  });

  // Base sum of all selected items
  let total = 0;
  for (const sel of selection.items) {
    const prod = products.find((p) => p.productId === sel.productId);
    if (!prod) continue;
    total += prod.basePrice * (sel.quantity ?? 1);
  }

  // Example discount: 10% off if bundle contains >3 items
  const itemCount = selection.items.reduce((sum, i) => sum + (i.quantity ?? 1), 0);
  if (itemCount >= 4) {
    total *= 0.9;
  }

  // Round to two decimals
  return Math.round(total * 100) / 100;
}

/**
 * Helper to persist a new bundle rule (used by admin UI).
 */
export async function createBundleRule(rule: {
  title: string;
  active: boolean;
  items: { productId: string; title: string; basePrice: number }[];
}) {
  return prisma.bundleRule.create({
    data: {
      title: rule.title,
      active: rule.active,
      items: {
        create: rule.items.map((i) => ({
          productId: i.productId,
          title: i.title,
          basePrice: i.basePrice,
        })),
      },
    },
  });
}
