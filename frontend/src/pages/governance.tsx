/**
 * GovernancePage — BATCH-20/TASK-02
 *
 * Full Governance Queue page replacing the /governance placeholder.
 * Shows all pending governance approvals with approve/deny actions.
 * Real-time refresh after each action.
 */

import { useEffect, useState, useCallback } from "react";
import { getPending, approveDecision, denyDecision } from "@/api/governance";
import type { PendingApproval } from "@/api/governance";
import { ApprovalCard } from "@/components/governance/approval-card";

export default function GovernancePage() {
  const [items, setItems] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPending = useCallback(async () => {
    try {
      const data = await getPending();
      setItems(data.pending);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pending approvals");
    } finally {
      setLoading(false);
    }
  }, []);

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
        setError(err instanceof Error ? err.message : "Failed to load pending approvals");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  async function handleApprove(id: string) {
    await approveDecision(id);
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  async function handleDeny(id: string, amendment?: string) {
    await denyDecision(id, amendment);
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  if (loading) {
    return (
      <div className="space-y-6" data-testid="governance-page">
        <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>
        <p className="text-muted-foreground">Loading pending approvals…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6" data-testid="governance-page">
        <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>
        <div
          className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-800"
          data-testid="governance-error"
        >
          <p className="font-medium">Error loading governance queue</p>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="governance-page">
      <h1 className="text-2xl font-bold tracking-tight">Governance Queue</h1>

      {items.length === 0 ? (
        <div className="rounded-lg border bg-card p-6 text-center" data-testid="governance-empty">
          <p className="text-muted-foreground">No pending approvals</p>
        </div>
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
