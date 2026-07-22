import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { listPlugins, installPlugin, type Plugin } from "@/api/exports";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Puzzle, Plus, Loader2, Search } from "lucide-react";
import { toast } from "sonner";

export default function PluginsPage() {
  const [searchText, setSearchText] = useState("");
  const [newPluginName, setNewPluginName] = useState("");
  const [newPluginDesc, setNewPluginDesc] = useState("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["plugins"],
    queryFn: listPlugins,
  });

  // F1.5c: invalidation declared in meta — cache-owned, survives unmount.
  const installMutation = useMutation({
    mutationFn: installPlugin,
    mutationKey: ["plugins", "install"],
    meta: {
      invalidateQueries: [["plugins"]],
    },
    onSuccess: () => {
      toast.success("Plugin installed");
      setNewPluginName("");
      setNewPluginDesc("");
    },
    onError: (_err) => {
      toast.error("Installation failed");
    },
  });

  const plugins = data?.plugins ?? [];
  const filtered = plugins.filter(
    (p) =>
      p.name.toLowerCase().includes(searchText.toLowerCase()) ||
      p.description.toLowerCase().includes(searchText.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Plugins</h1>
        <p className="text-muted-foreground">
          Browse and manage platform plugins.
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search plugins..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="pl-9"
          aria-label="Search plugins"
        />
      </div>

      {/* Install New Plugin */}
      <Card data-testid="plugin-install-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Install Plugin
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">Plugin Name</label>
              <Input
                placeholder="my-plugin"
                value={newPluginName}
                onChange={(e) => setNewPluginName(e.target.value)}
                data-testid="plugin-name-input"
                aria-label="Plugin name"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground mb-1 block">Description</label>
              <Input
                placeholder="Plugin description..."
                value={newPluginDesc}
                onChange={(e) => setNewPluginDesc(e.target.value)}
                data-testid="plugin-desc-input"
                aria-label="Plugin description"
              />
            </div>
            <Button
              onClick={() =>
                installMutation.mutate({
                  name: newPluginName,
                  description: newPluginDesc,
                })
              }
              disabled={!newPluginName.trim() || installMutation.isPending}
              data-testid="plugin-install-btn"
            >
              {installMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Install
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Plugin List */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="text-sm text-destructive p-4" data-testid="plugins-error">
          Failed to load plugins.{" "}
          <button onClick={() => refetch()} className="underline">
            Retry
          </button>
        </div>
      ) : (
        <div className="space-y-3" data-testid="plugin-list">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No plugins found{searchText ? ` for "${searchText}"` : ""}.</p>
            </div>
          ) : (
            filtered.map((plugin: Plugin) => (
              <Card key={plugin.name} data-testid={`plugin-card-${plugin.name}`}>
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <Puzzle className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{plugin.name}</span>
                        <Badge variant="outline" className="text-xs">
                          v{plugin.version}
                        </Badge>
                        {plugin.enabled ? (
                          <Badge className="text-xs bg-success/10 text-success">Enabled</Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs">Disabled</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {plugin.description || "No description"}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
          <p className="text-sm text-muted-foreground">
            {data?.total ?? 0} plugin{(data?.total ?? 0) !== 1 ? "s" : ""} total
          </p>
        </div>
      )}
    </div>
  );
}
