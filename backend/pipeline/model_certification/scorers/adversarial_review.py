"""Adversarial review scorer — uses planted-error cases.

Metrics: weakness_detection_rate, citation_mismatch_detection,
         overclaim_detection, false_alarm_rate, actionable_feedback_rate

Planted errors include: unsupported claims, missing controls,
citation mismatches, overclaiming, contradictory evidence, missing limitations.
"""

from __future__ import annotations

from backend.pipeline.model_certification.stage_scorer import StageScorer


class AdversarialReviewScorer(StageScorer):
    stage = "adversarial_review"

    def score(self, raw_output, parsed_output, case, gold=None):
        text = (raw_output or "").lower()

        if gold is None or not gold.planted_errors:
            # No planted errors to check — can only score general quality
            return {
                "weakness_detection_rate": 0.0,
                "citation_mismatch_detection": 0.0,
                "overclaim_detection": 0.0,
                "false_alarm_rate": 0.0,
                "actionable_feedback_rate": 0.0,
            }

        planted = gold.planted_errors
        total_planted = len(planted)
        if total_planted == 0:
            return {k: 1.0 for k in (
                "weakness_detection_rate", "citation_mismatch_detection",
                "overclaim_detection", "false_alarm_rate", "actionable_feedback_rate",
            )}

        # Check how many planted errors were detected
        detected = 0
        mismatch_detected = 0
        overclaim_detected = 0
        mismatch_planted = 0
        overclaim_planted = 0

        for error in planted:
            error_type = error.get("type", "")
            indicator = str(error.get("indicator", error.get("text", ""))).lower()

            if indicator and indicator in text:
                detected += 1

            if error_type == "citation_mismatch":
                mismatch_planted += 1
                if indicator and indicator in text:
                    mismatch_detected += 1

            if error_type == "overclaim":
                overclaim_planted += 1
                if indicator and indicator in text:
                    overclaim_detected += 1

        weakness_rate = detected / total_planted

        # Citation mismatch detection
        citation_mismatch = mismatch_detected / max(mismatch_planted, 1)

        # Overclaim detection
        overclaim = overclaim_detected / max(overclaim_planted, 1)

        # False alarm rate: count how many "issues" are mentioned that
        # aren't planted errors (heuristic: look for "issue/problem/concern")
        issue_markers = text.count("issue") + text.count("problem") + text.count("concern") + text.count("flaw")
        detected_count = detected
        false_alarms = max(0, issue_markers - detected_count)
        false_alarm_rate = min(1.0, false_alarms / max(total_planted, 1))

        # Actionable feedback rate: how many detected errors have actionable suggestions
        actionable_keywords = ["suggest", "recommend", "should", "improve", "fix", "correct"]
        actionable = sum(1 for k in actionable_keywords if k in text)
        actionable_rate = min(1.0, actionable / max(detected, 1))

        return {
            "weakness_detection_rate": round(weakness_rate, 3),
            "citation_mismatch_detection": round(citation_mismatch, 3),
            "overclaim_detection": round(overclaim, 3),
            "false_alarm_rate": round(false_alarm_rate, 3),
            "actionable_feedback_rate": round(actionable_rate, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["weakness_detection_rate"] < 0.3:
            failures.append("Low weakness detection rate")
        if scores["false_alarm_rate"] > 0.5:
            failures.append("High false alarm rate")
        if scores["overclaim_detection"] < 0.3:
            failures.append("Low overclaim detection")
        return failures
