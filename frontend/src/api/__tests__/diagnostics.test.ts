/**
 * F1.6.1 — diagnostics runtime-error contract tests.
 *
 * Verifies:
 *   - happy path: 202 with matching event_id accepted
 *   - malformed 2xx response → ApiContractError (decoder)
 *   - ack event_id mismatch → ApiContractError (client postcondition)
 *   - transport failure → ApiError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchVoid: vi.fn(),
  apiFetchUnchecked: vi.fn(),
  apiFetchBlob: vi.fn(),
  apiFetchFormData: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
      this.name = "ApiError";
    }
  },
}));

import { apiFetchJson as mockApiFetchJson } from "@/api/client";
import { ApiContractError } from "@/api/contracts/common";
import { sendRuntimeErrorReport } from "@/api/clients/diagnostics-client";
import type { ClientRuntimeErrorReport } from "@/api/contracts/diagnostics";

function makeReport(eventId = "evt-abc-123"): ClientRuntimeErrorReport {
  return {
    schema_version: "client_runtime_error_v1",
    event_id: eventId,
    category: "render_error",
    route: "/dashboard",
    component_stack: "in ComponentA\nin RouteBoundary",
    error_name: "TypeError",
    sanitized_message: "A component failed while rendering.",
    correlation_id: null,
    build_version: "abc1234",
    occurred_at: "2026-07-23T01:00:00Z",
  };
}

describe("sendRuntimeErrorReport (F1.6.1)", () => {
  beforeEach(() => {
    vi.mocked(mockApiFetchJson).mockReset();
  });

  it("happy path: 202 with matching event_id resolves with ack", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValueOnce({
      status: "accepted",
      event_id: "evt-abc-123",
    });
    const ack = await sendRuntimeErrorReport(makeReport("evt-abc-123"));
    expect(ack.status).toBe("accepted");
    expect(ack.event_id).toBe("evt-abc-123");
  });

  it("malformed 2xx (missing event_id) rejected as ApiContractError", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValueOnce({ status: "accepted" });
    await expect(sendRuntimeErrorReport(makeReport())).rejects.toBeInstanceOf(ApiContractError);
  });

  it("malformed 2xx (wrong status value) rejected as ApiContractError", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValueOnce({
      status: "queued",
      event_id: "evt-abc-123",
    });
    await expect(sendRuntimeErrorReport(makeReport())).rejects.toBeInstanceOf(ApiContractError);
  });

  it("[V3-ack] event_id mismatch rejected as ApiContractError (client postcondition)", async () => {
    // Server echoes a DIFFERENT event_id than what was submitted.
    vi.mocked(mockApiFetchJson).mockResolvedValueOnce({
      status: "accepted",
      event_id: "different-id-from-server",
    });
    const report = makeReport("evt-submitted-001");
    await expect(sendRuntimeErrorReport(report)).rejects.toMatchObject({
      name: "ApiContractError",
      code: "api_response_contract_mismatch",
      endpointId: "diagnostics.runtimeError",
    });
  });

  it("transport failure propagates (caller must swallow)", async () => {
    const { ApiError } = await import("@/api/client");
    vi.mocked(mockApiFetchJson).mockRejectedValueOnce(
      new ApiError(429, "rate limited"),
    );
    await expect(sendRuntimeErrorReport(makeReport())).rejects.toMatchObject({
      name: "ApiError",
      status: 429,
    });
  });
});
