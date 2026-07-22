/**
 * FixSectionButton — Triggers section regeneration with confirmation.
 *
 * Shows on failing sections with refinement_available=true. Opens a
 * confirmation dialog before calling the LLM. No optimistic updates —
 * waits for API response then refetches.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Wrench,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { refineSection } from "@/api/ideas";
import { toast } from "sonner";

export function FixSectionButton({
  ideaId,
  sectionKey,
  sectionLabel,
  currentHash,
  failureHints,
}: {
  ideaId: number;
  sectionKey: string;
  sectionLabel: string;
  currentHash: string;
  failureHints?: string[];
}) {
  const queryClient = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);

  // F1.5c: success-path invalidations declared in meta — cache-owned,
  // survives unmount. onError invalidation (409-conflict refresh) stays
  // component-level: errors don't change backend state, and cache-level
  // onError is out of scope here.
  const mutation = useMutation({
    mutationFn: () =>
      refineSection(
        ideaId,
        sectionKey,
        currentHash,
        failureHints ? { failure_hints: failureHints } : undefined,
      ),
    mutationKey: ["idea", ideaId, "refine-section", sectionKey],
    meta: {
      invalidateQueries: [
        ["idea", ideaId],
        ["section-revisions", ideaId, sectionKey],
      ],
    },
    onSuccess: (data) => {
      const improved =
        data.quality_checks_after.filter((c) => c.passed).length >=
        data.quality_checks_before.filter((c) => c.passed).length;
      toast.success(
        improved
          ? "Section regenerated — quality improved"
          : "Section regenerated — see revision history",
      );
      setConfirmed(false);
    },
    onError: (err: Error) => {
      if (err.message.includes("409") || err.message.includes("CONFLICT")) {
        toast.error("Section was modified elsewhere — refreshing");
        queryClient.invalidateQueries({ queryKey: ["idea", ideaId] });
      } else if (err.message.includes("422") || err.message.includes("RECEIPT")) {
        toast.error("Provider cannot produce model receipt for refinement");
      } else {
        toast.error("Refinement failed", { description: err.message });
      }
      setConfirmed(false);
    },
  });

  if (mutation.isPending) {
    return (
      <Button variant="outline" size="sm" disabled>
        <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
        Regenerating...
      </Button>
    );
  }

  if (!confirmed) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setConfirmed(true)}
        data-testid={`fix-button-${sectionKey}`}
      >
        <Wrench className="mr-1.5 h-3 w-3" />
        Fix Section
      </Button>
    );
  }

  // Confirmation state
  return (
    <div className="flex items-center gap-2" data-testid={`fix-confirm-${sectionKey}`}>
      <AlertCircle className="h-3 w-3 text-warning" />
      <span className="text-xs text-muted-foreground">
        Regenerate {sectionLabel}?
      </span>
      <Button
        variant="default"
        size="sm"
        onClick={() => mutation.mutate()}
        data-testid={`fix-confirm-yes-${sectionKey}`}
      >
        Yes, regenerate
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setConfirmed(false)}
      >
        Cancel
      </Button>
    </div>
  );
}
