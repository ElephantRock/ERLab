import { useSettings } from "@/contexts/settings-context";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function Settings() {
  const { apiUrl, apiKey, theme, setApiUrl, setApiKey, setTheme } = useSettings();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure your API connection and preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">API Connection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">API Base URL</label>
            <Input
              placeholder="http://localhost:8000"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to use the Vite proxy (defaults to localhost:8000 in dev).
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              placeholder="Optional API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Appearance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Button
              variant={theme === "light" ? "default" : "outline"}
              onClick={() => setTheme("light")}
            >
              Light
            </Button>
            <Button
              variant={theme === "dark" ? "default" : "outline"}
              onClick={() => setTheme("dark")}
            >
              Dark
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
