/**
 * F1.6.1 — Diagnostics transport client.
 *
 * F1.6.1 [V3-2]: the transport layer MAY reject. It is distinct from
 * the never-throw reporter (lib/runtime-error-reporter.ts) which
 * orchestrates sanitization, deduplication, and swallows all transport
 * failures.
 *
 * F1.6.1 [V3-ack]: the acknowledgment decoder validates only the SHAPE
 * of the response. Equality between the returned event_id and the
 * submitted report's event_id is enforced as a CLIENT POSTCONDITION
 * here. A static decoder cannot know the submitted request ID, so this
 * is the natural place to assert it.
 */

import { callContract } from "@/api/contracts/common";
import { ApiContractError } from "@/api/contracts/common";
import {
  runtimeErrorContract,
  type ClientRuntimeErrorReport,
  type RuntimeErrorAcknowledgment,
} from "@/api/contracts/diagnostics";

/**
 * Submit a runtime-error report to the governed backend endpoint.
 *
 * Resolves with the validated acknowledgment. The acknowledgment's
 * event_id MUST equal the submitted report's event_id — if not, this
 * function rejects with an ApiContractError.
 *
 * May reject on:
 *   - transport failure (network, 5xx) → ApiError
 *   - response shape mismatch → ApiContractError
 *   - event_id mismatch (postcondition) → ApiContractError
 *   - rate limit (429) → ApiError
 *   - origin/size rejection (403/413) → ApiError
 *
 * Callers that cannot propagate these failures (e.g. an error boundary)
 * must use `reportRuntimeError` instead, which swallows them.
 */
export async function sendRuntimeErrorReport(
  report: ClientRuntimeErrorReport,
): Promise<RuntimeErrorAcknowledgment> {
  const ack = await callContract(runtimeErrorContract, { body: report });
  if (ack.event_id !== report.event_id) {
    throw new ApiContractError(
      "api_response_contract_mismatch",
      "diagnostics.runtimeError",
      "acknowledgment event_id did not match submitted report event_id",
      202,
    );
  }
  return ack;
}

export type { ClientRuntimeErrorReport, RuntimeErrorAcknowledgment };
