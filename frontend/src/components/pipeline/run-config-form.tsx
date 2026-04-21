import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { PipelineRunRequest } from "@/api/types";
import { Search, Loader2 } from "lucide-react";

interface RunConfigFormProps {
  onSubmit: (config: PipelineRunRequest) => void;
  isLoading?: boolean;
}

export function RunConfigForm({ onSubmit, isLoading }: RunConfigFormProps) {
  const [domain, setDomain] = useState("");
  const [maxGaps, setMaxGaps] = useState(10);
  const [ideasPerRound, setIdeasPerRound] = useState(5);
  const [searchQueries, setSearchQueries] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const config: PipelineRunRequest = {
      domain: domain || undefined,
      max_gaps: maxGaps,
      ideas_per_round: ideasPerRound,
      search_queries: searchQueries
        ? searchQueries.split(",").map((q) => q.trim()).filter(Boolean)
        : undefined,
    };
    onSubmit(config);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Pipeline Configuration</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Research Domain</label>
            <Input
              placeholder="e.g., machine learning, nlp, computer vision"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Gaps</label>
              <Input
                type="number"
                min={1}
                max={50}
                value={maxGaps}
                onChange={(e) => setMaxGaps(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Ideas Per Round</label>
              <Input
                type="number"
                min={1}
                max={20}
                value={ideasPerRound}
                onChange={(e) => setIdeasPerRound(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Search Queries (comma-separated)</label>
            <Input
              placeholder="transformer attention, few-shot learning"
              value={searchQueries}
              onChange={(e) => setSearchQueries(e.target.value)}
            />
          </div>

          <Button type="submit" disabled={isLoading} className="w-full">
            {isLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Search className="mr-2 h-4 w-4" />
            )}
            {isLoading ? "Starting..." : "Start Pipeline"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
