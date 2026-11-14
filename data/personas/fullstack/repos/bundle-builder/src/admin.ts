import { useEffect, useState } from "react";
import { Form, TextField, Button, Card, Stack } from "@shopify/polaris";
import { createBundleRule, BundleRule } from "./bundle";
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

/**
 * Simple admin panel for managing bundle rules.
 * Staff can add a rule with a title and a JSON list of items.
 */
export function AdminPanel() {
  const [title, setTitle] = useState("");
  const [itemsJson, setItemsJson] = useState("[]");
  const [rules, setRules] = useState<BundleRule[]>([]);

  // Load existing rules on mount
  useEffect(() => {
    prisma.bundleRule.findMany({ include: { items: true } }).then(setRules);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const items = JSON.parse(itemsJson);
    await createBundleRule({ title, active: true, items });
    // Refresh list
    const refreshed = await prisma.bundleRule.findMany({ include: { items: true } });
    setRules(refreshed);
    setTitle("");
    setItemsJson("[]");
  };

  return (
    <Card title="Bundle Rules">
      <Card.Section>
        <Form onSubmit={handleSubmit}>
          <Stack vertical>
            <TextField label="Rule Title" value={title} onChange={setTitle} />
            <TextField
              label="Items (JSON array)"
              value={itemsJson}
              onChange={setItemsJson}
              multiline
            />
            <Button submit primary>
              Save Rule
            </Button>
          </Stack>
        </Form>
      </Card.Section>
      <Card.Section title="Existing Rules">
        {rules.map((r) => (
          <div key={r.id}>
            <strong>{r.title}</strong> – {r.active ? "Active" : "Inactive"}
          </div>
        ))}
      </Card.Section>
    </Card>
  );
}
