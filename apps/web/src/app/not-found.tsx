import { EmptyState } from "@/components/EmptyState";
import { LinkButton } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="That page does not exist in GigBid."
      action={
        <LinkButton href="/inbox" variant="primary">
          Back to the inbox
        </LinkButton>
      }
    />
  );
}
