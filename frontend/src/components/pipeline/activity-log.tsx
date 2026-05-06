import { useEffect, useRef } from "react";
import { ScrollText } from "lucide-react";

export interface ProgressMessage {
  event_type: string;
  stage: string;
  step: string;
  message: string;
  progress_pct: number;
  timestamp: number;
}

interface ActivityLogProps {
  messages: ProgressMessage[];
  autoScroll?: boolean;
}

const stageIcons: Record<string, string> = {
  literature_search: "📚",
  ingestion: "📥",
  gap_analysis: "🔍",
  idea_generation: "💡",
  novelty_checking: "🆕",
  feasibility_scoring: "📊",
  mechanical_metrics: "⚙️",
  proposal_synthesis: "📝",
  export: "📤",
};

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function ActivityLog({ messages, autoScroll = true }: ActivityLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, autoScroll]);

  if (messages.length === 0) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm p-4">
        <ScrollText className="h-4 w-4" />
        <span>Waiting for pipeline activity...</span>
      </div>
    );
  }

  return (
    <div className="max-h-64 overflow-y-auto rounded-md border bg-card text-sm">
      {messages.map((msg, idx) => (
        <div
          key={idx}
          className="flex items-start gap-2 px-3 py-1.5 border-b last:border-b-0 hover:bg-accent/5"
        >
          <span className="text-base leading-5 shrink-0">
            {stageIcons[msg.stage] || "🔄"}
          </span>
          <span className="text-muted-foreground text-xs shrink-0 mt-0.5">
            {formatTime(msg.timestamp)}
          </span>
          <span className="text-foreground flex-1">{msg.message}</span>
          {msg.progress_pct > 0 && msg.step !== "complete" && (
            <span className="text-muted-foreground text-xs shrink-0">
              {Math.round(msg.progress_pct * 100)}%
            </span>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
