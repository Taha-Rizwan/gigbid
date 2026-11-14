/**
 * Types shared across the bundle builder.
 */

export interface BundleItem {
  id: number;
  productId: string;
  title: string;
  basePrice: number;
}

/**
 * A rule groups a set of items that can be combined.
 */
export interface BundleRule {
  id: number;
  title: string;
  active: boolean;
  items: BundleItem[];
}

/**
 * Shopper's selection sent from the storefront form.
 */
export interface BundleSelection {
  items: {
    productId: string;
    quantity?: number;
  }[];
}
