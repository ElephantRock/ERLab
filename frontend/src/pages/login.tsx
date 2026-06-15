/** Login / Register page (BATCH-28). */

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"login" | "register" | "forgot">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    try {
      if (mode === "forgot") {
        const res = await fetch("/api/v1/auth/forgot-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error?.message || data?.detail || "Reset failed");
        setSuccess(data.message || "Reset instructions sent.");
        return;
      }
      if (mode === "register") {
        await register(username, email, password);
      } else {
        await login(username, password);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        "Authentication failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl text-center">
            {mode === "login" ? "Sign In" : mode === "register" ? "Create Account" : "Reset Password"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="auth-form">
            {(mode === "login" || mode === "register") && (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="username">
                  Username
                </label>
                <Input
                  id="username"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  data-testid="username-input"
                />
              </div>
            )}

            {(mode === "register" || mode === "forgot") && (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="email">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  data-testid="email-input"
                />
              </div>
            )}

            {(mode === "login" || mode === "register") && (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="password">
                  Password
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  data-testid="password-input"
                />
              </div>
            )}

            {error && (
              <p className="text-sm text-destructive" data-testid="auth-error">
                {error}
              </p>
            )}

            {success && (
              <p className="text-sm text-success" data-testid="auth-success">
                {success}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={submitting}
              data-testid="auth-submit"
            >
              {submitting
                ? "Please wait..."
                : mode === "login"
                  ? "Sign In"
                  : mode === "register"
                    ? "Create Account"
                    : "Send Reset Link"}
            </Button>

            <div className="text-center text-sm space-y-1">
              {mode === "login" && (
                <>
                  <div>
                    <Button
                      variant="link"
                      type="button"
                      onClick={() => { setMode("forgot"); setError(""); setSuccess(""); }}
                      data-testid="switch-to-forgot"
                    >
                      Forgot password?
                    </Button>
                  </div>
                  <div>
                    Don't have an account?{" "}
                    <Button
                      variant="link"
                      type="button"
                      onClick={() => { setMode("register"); setError(""); setSuccess(""); }}
                      data-testid="switch-to-register"
                    >
                      Register
                    </Button>
                  </div>
                </>
              )}
              {mode === "register" && (
                <span>
                  Already have an account?{" "}
                  <Button
                    variant="link"
                    type="button"
                    onClick={() => { setMode("login"); setError(""); setSuccess(""); }}
                    data-testid="switch-to-login"
                  >
                    Sign In
                  </Button>
                </span>
              )}
              {mode === "forgot" && (
                <span>
                  Remember your password?{" "}
                  <Button
                    variant="link"
                    type="button"
                    onClick={() => { setMode("login"); setError(""); setSuccess(""); }}
                    data-testid="switch-to-login-from-forgot"
                  >
                    Sign In
                  </Button>
                </span>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
