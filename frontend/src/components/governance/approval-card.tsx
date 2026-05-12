/**
 * ApprovalCard — BATCH-20/TASK-01
 *
 * Card component for a single pending governance approval.
 * Shows item summary, type badge, and approve/deny actions.
 * Deny action reveals an optional amendment text input.
 */

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { PendingApproval } from "@/api/governance";

interface ApprovalCardProps {
  item: PendingApproval;
  onApprove: (id: string) => Promise<void>;
  onDeny: (id: string, amendment?: string) => Promise<void>;
}

export function ApprovalCard({ item, onApprove, onDeny }: ApprovalCardProps) {
  const [denying, setDenying] = useState(false);
  const [amendment, setAmendment] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleApprove() {
    setLoading(true);
    try {
      await onApprove(item.id);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeny() {
    if (!denying) {
      setDenying(true);
      return;
    }
    setLoading(true);
    try {
      await onDeny(item.id, amendment || undefined);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card data-testid={`approval-card-${item.id}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-medium leading-tight">{item.summary}</h3>
            <div className="mt-2">
              <Badge variant="outline" className="text-xs">
                {item.type}
              </Badge>
            </div>
          </div>

          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={handleApprove}
                disabled={loading}
                data-testid={`approve-btn-${item.id}`}
              >
                Approve
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={handleDeny}
                disabled={loading}
                data-testid={`deny-btn-${item.id}`}
              >
                {denying ? "Confirm Deny" : "Deny"}
              </Button>
            </div>

            {denying && (
              <input
                type="text"
                placeholder="Optional amendment..."
                value={amendment}
                onChange={(e) => setAmendment(e.target.value)}
                className="w-56 rounded-md border border-input bg-background px-3 py-1.5 text-xs ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                data-testid={`amendment-input-${item.id}`}
              />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
