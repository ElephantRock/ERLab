import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { triggerAutonomous } from "@/api/pipeline";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Bot } from "lucide-react";
import { toast } from "sonner";

interface AutonomousFormProps {
  onCycleStarted?: (cycleId: string) => void;
}

export function AutonomousForm({ onCycleStarted }: AutonomousFormProps) {
  const [domain, setDomain] = useState("");
  const [maxRuns, setMaxRuns] = useState(3);

  const mutation = useMutation({
    mutationFn: () => triggerAutonomous({ domain: domain || undefined, max_runs: maxRuns }),
    onSuccess: (data) => {
      toast.success(`Autonomous cycle started (${data.cycle_id})`);
      onCycleStarted?.(data.cycle_id);
    },
    onError: (err) => {
      toast.error(err.message || "Failed to start autonomous cycle");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          Autonomous Cycle
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Run multiple pipeline iterations automatically, using ideas from each round to inform the next.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Domain</label>
              <Input
                placeholder="AI/NLP"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Runs</label>
              <Input
                type="number"
                min={1}
                max={20}
                value={maxRuns}
                onChange={(e) => setMaxRuns(Number(e.target.value))}
              />
            </div>
          </div>
          <Button type="submit" disabled={mutation.isPending} className="w-full">
            {mutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Bot className="mr-2 h-4 w-4" />
            )}
            {mutation.isPending ? "Starting..." : "Start Autonomous Cycle"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
