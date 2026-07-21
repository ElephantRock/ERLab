import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Play,
  Lightbulb,
  ChevronRight,
  X,
  FlaskConical,
  Sparkles,
} from "lucide-react";

/**
 * OnboardingOverlay — 3-step guided introduction for first-time users.
 *
 * Shows only when:
 *  - localStorage doesn't have "erock_onboarding_complete"
 *  - There are 0 completed pipeline runs
 *
 * Steps:
 *  1. "What Elephant Rock Does" — value proposition
 *  2. "Enter Your Research Topic" — quick-start form
 *  3. "Understanding Your Results" — what to expect
 *
 * After completion, sets localStorage flag and never shows again.
 */

interface OnboardingOverlayProps {
  /** Called when user clicks "Start Research" from step 2 */
  onStartPipeline: (topic: string) => void;
  /** Called when user dismisses the overlay */
  onDismiss: () => void;
}

const STEPS = [
  {
    icon: FlaskConical,
    title: "Welcome to Elephant Rock",
    description:
      "An AI research platform that discovers academic papers, identifies gaps in the literature, and generates novel research proposals with full methodology, evaluation plans, and risk analysis.",
    detail:
      "Give it a research topic, wait ~20 minutes, and receive publication-ready proposals you can export as Markdown or LaTeX.",
    color: "text-info bg-info/10",
  },
  {
    icon: Play,
    title: "Start Your First Pipeline",
    description:
      "Enter a research topic below. The pipeline will search academic databases, analyze hundreds of papers, and generate novel ideas with full proposals.",
    detail: "",
    color: "text-success bg-success/10",
  },
  {
    icon: Lightbulb,
    title: "What You'll Get",
    description:
      "After the pipeline completes, you'll see scored research ideas with novelty ratings, feasibility assessments, and detailed proposals covering:",
    detail: "",
    color: "text-warning bg-warning/10",
  },
];

const PROPOSAL_SECTIONS = [
  "Problem Statement & Motivation",
  "Proposed Method with technical detail",
  "Evaluation Plan with metrics",
  "Expected Contributions",
  "Risk Analysis & Mitigation",
  "Full References with real DOIs",
];

export function OnboardingOverlay({ onStartPipeline, onDismiss }: OnboardingOverlayProps) {
  const [step, setStep] = useState(0);
  const [topic, setTopic] = useState("");

  function handleDismiss() {
    localStorage.setItem("erock_onboarding_complete", "true");
    onDismiss();
  }

  function handleNext() {
    if (step < 2) {
      setStep(step + 1);
    }
  }

  function handleStart() {
    if (topic.trim()) {
      localStorage.setItem("erock_onboarding_complete", "true");
      onStartPipeline(topic.trim());
    }
  }

  // Current onboarding step. STEPS has exactly 3 entries and `step` is
  // bounded to [0, 2] by handleNext (setStep only when step < 2). The
  // explicit guard narrows away the `| undefined` that noUncheckedIndexedAccess
  // adds to array index access; if a future change breaks the invariant,
  // this returns null instead of crashing on a property access.
  const current = STEPS[step];
  if (!current) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <Card className="w-full max-w-lg mx-4 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-4">
          <div className="flex items-center gap-2">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={`h-2 rounded-full transition-[width] ${
                  i === step
                    ? "w-8 bg-primary"
                    : i < step
                      ? "w-2 bg-primary/60"
                      : "w-2 bg-muted"
                }`}
              />
            ))}
          </div>
          <button
            onClick={handleDismiss}
            className="text-muted-foreground hover:text-foreground p-1"
            data-testid="onboarding-skip"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <CardHeader className="pb-2">
          <div className="flex items-center gap-3">
            <div className={`rounded-full p-2 ${current.color}`}>
              {(() => {
                const Icon = current.icon;
                return <Icon className="h-5 w-5" />;
              })()}
            </div>
            <CardTitle className="text-xl">{current.title}</CardTitle>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Step 0: Welcome */}
          {step === 0 && (
            <>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {current.description}
              </p>
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm font-medium">{current.detail}</p>
              </div>
            </>
          )}

          {/* Step 1: Enter topic */}
          {step === 1 && (
            <>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {current.description}
              </p>
              <div className="space-y-3 pt-2">
                <input
                  type="text"
                  placeholder="Mechanistic Interpretability of Transformer Reasoning Chains..."
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleStart()}
                  className="flex h-12 w-full rounded-md border border-input bg-background px-4 py-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  data-testid="onboarding-topic-input"
                  autoFocus
                />
                <Button
                  onClick={handleStart}
                  disabled={!topic.trim()}
                  className="w-full h-11"
                  data-testid="onboarding-start-btn"
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  Start Research Pipeline
                </Button>
              </div>
            </>
          )}

          {/* Step 2: What you'll get */}
          {step === 2 && (
            <>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {current.description}
              </p>
              <ul className="space-y-2">
                {PROPOSAL_SECTIONS.map((section) => (
                  <li key={section} className="flex items-center gap-2 text-sm">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary flex-shrink-0" />
                    <span>{section}</span>
                  </li>
                ))}
              </ul>
              <div className="rounded-lg bg-warning/5 dark:bg-warning/20 border border-warning/30 dark:border-warning/40 p-3">
                <p className="text-xs text-warning dark:text-warning">
                  <strong>⏱ Timing:</strong> A "Quick Scan" takes ~3 minutes. A "Deep Research" run takes ~20 minutes. You can watch the progress in real-time.
                </p>
              </div>
            </>
          )}

          {/* Navigation */}
          {step !== 1 && (
            <div className="flex items-center justify-between pt-2">
              {step > 0 ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setStep(step - 1)}
                >
                  Back
                </Button>
              ) : (
                <div />
              )}
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDismiss}
                  data-testid="onboarding-skip-btn"
                >
                  Skip for now
                </Button>
                {step < 2 && (
                  <Button size="sm" onClick={handleNext}>
                    Next
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </Button>
                )}
                {step === 2 && (
                  <Button
                    size="sm"
                    onClick={handleDismiss}
                    data-testid="onboarding-got-it"
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Got it — let's go!
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
