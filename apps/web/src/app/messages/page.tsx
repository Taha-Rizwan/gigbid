import { MessagesSquare } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";

export default function MessagesIndex() {
  return (
    <EmptyState
      icon={<MessagesSquare className="size-8" />}
      title="Select a conversation"
      description="Pick a thread to read it, see GigBid's suggested reply and approve, edit or reject it."
    />
  );
}
