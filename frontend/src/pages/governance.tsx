/**
 * GovernancePage — BATCH-20/TASK-02
 *
 * Full Governance Queue page replacing the /governance placeholder.
 * Shows all pending governance approvals with approve/deny actions.
 * Real-time refresh after each action.
 */

import { useEffect, useState } from "react";
import { getPending, approveDecision, denyDecision } from "@/api/governance";
import type { PendingApproval } from "@/api/governance";
import { ApprovalCard } from "@/components/governance/approval-card";
import { ErrorCard } from "@/components/ui/error-card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

export default function GovernancePage() {
  const [items, setItems] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getPending();
        if (cancelled) return;
        setItems(data.pending);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError("Failed to load pending approvals");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  async function handleApprove(id: string) {
    try {
      await approveDecision(id);
      toast.success("Approved");
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch {
      toast.error("Failed to approve");
    }
  }

  async function handleDeny(id: string, amendment?: string) {
    try {
      await denyDecision(id, amendment);
      toast.success("Denied");
      setItems((prev) => prev.filter((item) => item.id !== id));
    } catch {
      toast.error("Failed to deny");
    }
  }

  if (loading) {
    return (
      <div className="space-y-6" data-testid="governance-page">
        <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6" data-testid="governance-page">
        <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>
        <ErrorCard message="Failed to load pending approvals" testId="governance-error" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="governance-page">
      <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>

      {items.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="No pending approvals"
          message="The governance queue is empty. New approvals will appear here."
          testId="governance-empty"
        />
      ) : (
        <div className="space-y-3" data-testid="governance-list">
          {items.map((item) => (
            <ApprovalCard
              key={item.id}
              item={item}
              onApprove={handleApprove}
              onDeny={handleDeny}
            />
          ))}
        </div>
      )}
    </div>
  );
}
