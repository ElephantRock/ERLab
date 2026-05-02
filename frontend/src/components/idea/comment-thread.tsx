import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listComments, addComment } from "@/api/collaboration";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageSquare, Loader2, Send, CornerDownRight } from "lucide-react";
import { toast } from "sonner";

interface CommentThreadProps {
  ideaId: number;
}

export function CommentThread({ ideaId }: CommentThreadProps) {
  const [author, setAuthor] = useState("anonymous");
  const [content, setContent] = useState("");
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["comments", ideaId],
    queryFn: () => listComments(ideaId),
  });

  const mutation = useMutation({
    mutationFn: () =>
      addComment(ideaId, { author, content, parent_id: replyTo }),
    onSuccess: () => {
      toast.success("Comment added");
      queryClient.invalidateQueries({ queryKey: ["comments", ideaId] });
      setContent("");
      setReplyTo(null);
    },
    onError: (err) => {
      toast.error(err.message || "Failed to add comment");
    },
  });

  const comments = data?.comments ?? [];

  // Organize into threads: top-level + replies
  const topLevel = comments.filter((c) => c.parent_id === null);
  const getReplies = (parentId: number) =>
    comments.filter((c) => c.parent_id === parentId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <MessageSquare className="h-4 w-4" />
          Comments ({data?.total ?? 0})
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Comment list */}
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading comments...</p>
        ) : topLevel.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No comments yet. Be the first!
          </p>
        ) : (
          <div className="space-y-3">
            {topLevel.map((comment) => (
              <div key={comment.id} className="space-y-2">
                <CommentEntry
                  comment={comment}
                  onReply={() => setReplyTo(comment.id)}
                />
                {/* Replies */}
                {getReplies(comment.id).map((reply) => (
                  <div key={reply.id} className="ml-6 border-l-2 border-muted pl-3">
                    <CommentEntry comment={reply} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Add comment form */}
        <div className="border-t pt-4 space-y-2">
          {replyTo && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <CornerDownRight className="h-3 w-3" />
              Replying to comment #{replyTo}
              <button
                className="underline hover:text-foreground"
                onClick={() => setReplyTo(null)}
              >
                Cancel
              </button>
            </div>
          )}
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Your name"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              className="w-28 rounded-md border border-input bg-background px-2 py-1 text-sm"
            />
            <input
              type="text"
              placeholder="Add a comment..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && content.trim()) {
                  mutation.mutate();
                }
              }}
              className="flex-1 rounded-md border border-input bg-background px-3 py-1 text-sm"
            />
            <Button
              size="sm"
              onClick={() => mutation.mutate()}
              disabled={!content.trim() || mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CommentEntry({
  comment,
  onReply,
}: {
  comment: { id: number; author: string; content: string; created_at: string };
  onReply?: () => void;
}) {
  return (
    <div className="group rounded-lg bg-muted/50 p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{comment.author}</span>
        <span className="text-xs text-muted-foreground">
          {new Date(comment.created_at).toLocaleDateString()}
        </span>
      </div>
      <p className="mt-1 text-sm">{comment.content}</p>
      {onReply && (
        <button
          className="mt-1 text-xs text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={onReply}
        >
          Reply
        </button>
      )}
    </div>
  );
}
