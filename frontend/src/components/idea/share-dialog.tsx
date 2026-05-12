import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { createShareLink } from "@/api/collaboration";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Share2, Loader2, Copy, Check } from "lucide-react";
import { toast } from "sonner";

interface ShareDialogProps {
  ideaId: number;
}

export function ShareDialog({ ideaId }: ShareDialogProps) {
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: () => createShareLink(ideaId),
    onSuccess: (data) => {
      const fullUrl = `${window.location.origin}${data.share_url}`;
      setShareUrl(fullUrl);
      toast.success("Share link created");
    },
    onError: (err) => {
      toast.error(err.message || "Failed to create share link");
    },
  });

  const handleCopy = async () => {
    if (shareUrl) {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success("Link copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Share2 className="h-4 w-4" />
          Share
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {shareUrl ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={shareUrl}
                className="flex-1 rounded-md border border-input bg-muted px-3 py-1.5 text-sm font-mono"
              />
              <Button size="sm" variant="outline" onClick={handleCopy}>
                {copied ? (
                  <Check className="h-4 w-4 text-success" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Anyone with this link can view this idea (read-only).
            </p>
          </div>
        ) : (
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            variant="outline"
            size="sm"
          >
            {mutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Share2 className="mr-2 h-4 w-4" />
            )}
            Generate Share Link
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
