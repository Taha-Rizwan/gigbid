import { json, LoaderFunction, ActionFunction } from "@remix-run/node";
import { useLoaderData, Form } from "@remix-run/react";
import { PrismaClient } from "@prisma/client";
import { BundleRule, BundleSelection } from "./types";
import { calculateBundlePrice } from "./bundle";
import { AdminPanel } from "./admin";
import { PolarisProvider } from "@shopify/polaris";

const prisma = new PrismaClient();

/**
 * Loader fetches all active bundle rules for the storefront.
 */
export const loader: LoaderFunction = async () => {
  const rules = await prisma.bundleRule.findMany({
    where: { active: true },
    include: { items: true },
  });
  return json({ rules });
};

/**
 * Action receives shopper selections and returns the computed price.
 */
export const action: ActionFunction = async ({ request }) => {
  const formData = await request.formData();
  const selection: BundleSelection = {
    items: JSON.parse(formData.get("items") as string),
  };
  const price = await calculateBundlePrice(selection);
  return json({ price });
};

/**
 * Main storefront component.
 */
export default function BundleBuilder() {
  const { rules } = useLoaderData<typeof loader>();

  return (
    <PolarisProvider>
      <h2>Build Your Gift Box</h2>
      <Form method="post">
        {/* Render each rule as a selectable group */}
        {rules.map((rule: BundleRule) => (
          <div key={rule.id} style={{ marginBottom: "1rem" }}>
            <label>{rule.title}</label>
            <select name="items" multiple>
              {rule.items.map((item: any) => (
                <option key={item.id} value={item.productId}>
                  {item.title} – ${item.basePrice}
                </option>
              ))}
            </select>
          </div>
        ))}
        <button type="submit">Update Price</button>
      </Form>
    </PolarisProvider>
  );
}

/**
 * Optional admin route – mounted at /admin.
 */
export function AdminRoute() {
  return (
    <PolarisProvider>
      <AdminPanel />
    </PolarisProvider>
  );
}
