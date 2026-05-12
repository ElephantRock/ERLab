import { useState } from "react";
import { Button } from "@/components/ui/button";
import { submitGapFeedback } from "@/api/gaps";
import { toast } from "sonner";
import { Star } from "lucide-react";

interface GapFeedbackFormProps {
  gapId: number;
  currentRating?: number | null;
  currentNotes?: string | null;
  onSubmitted?: () => void;
}

export function GapFeedbackForm({ gapId, currentRating, currentNotes, onSubmitted }: GapFeedbackFormProps) {
  const [rating, setRating] = useState<number | null>(currentRating ?? null);
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [notes, setNotes] = useState(currentNotes ?? "");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await submitGapFeedback(gapId, rating, notes || undefined);
      toast.success("Feedback submitted");
      onSubmitted?.();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium">Rate this gap</h3>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => setRating(star)}
            onMouseEnter={() => setHoverRating(star)}
            onMouseLeave={() => setHoverRating(null)}
            className="p-1 hover:scale-110 transition-transform"
            aria-label={`Rate ${star} star${star !== 1 ? "s" : ""}`}
          >
            <Star
              className={`h-5 w-5 ${
                (hoverRating ?? rating) !== null && star <= (hoverRating ?? rating)!
                  ? "fill-warning text-warning"
                  : "text-muted-foreground"
              }`}
            />
          </button>
        ))}
      </div>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Optional notes..."
        maxLength={2000}
        className="w-full min-h-[60px] rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
      />
      <p className="text-xs text-muted-foreground">{notes.length}/2000</p>
      <Button
        size="sm"
        disabled={!rating || submitting}
        onClick={handleSubmit}
      >
        {submitting ? "Submitting..." : "Submit Feedback"}
      </Button>
    </div>
  );
}
