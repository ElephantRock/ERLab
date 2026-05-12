import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitFeedback } from "@/api/ideas";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Star, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface FeedbackFormProps {
  ideaId: number;
  onSuccess?: () => void;
}

export function FeedbackForm({ ideaId, onSuccess }: FeedbackFormProps) {
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [notes, setNotes] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => submitFeedback(ideaId, { rating, notes: notes || null }),
    onSuccess: () => {
      toast.success("Feedback submitted");
      queryClient.invalidateQueries({ queryKey: ["idea", ideaId] });
      setRating(0);
      setNotes("");
      onSuccess?.();
    },
    onError: (err) => {
      toast.error(err.message || "Failed to submit feedback");
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feedback</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className="p-0.5 hover:scale-110 transition-transform"
              onMouseEnter={() => setHovered(star)}
              onMouseLeave={() => setHovered(0)}
              onClick={() => setRating(star)}
            >
              <Star
                className={cn(
                  "h-6 w-6",
                  (hovered || rating) >= star
                    ? "fill-warning text-warning"
                    : "text-muted-foreground",
                )}
              />
            </button>
          ))}
          <span className="ml-2 text-sm text-muted-foreground">
            {rating > 0 ? `${rating}/5` : "Select rating"}
          </span>
        </div>

        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          placeholder="Optional notes (max 2000 chars)..."
          value={notes}
          onChange={(e) => setNotes(e.target.value.slice(0, 2000))}
        />

        <Button
          onClick={() => mutation.mutate()}
          disabled={rating === 0 || mutation.isPending}
        >
          {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Submit Feedback
        </Button>
      </CardContent>
    </Card>
  );
}
