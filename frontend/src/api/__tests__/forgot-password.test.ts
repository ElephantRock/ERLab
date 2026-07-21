/**
 * F1.1b — forgotPassword contract tests.
 *
 * Verifies the JsonContract<ForgotPasswordResult> runtime decoder:
 *   valid response          accepted
 *   HTTP error              rejected as ApiError
 *   missing message         rejected as ApiContractError
 *   non-string message      rejected as ApiContractError
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the transport so forgotPassword's callContract uses our test data
vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchVoid: vi.fn(),
  apiFetchUnchecked: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) {
      super(detail);
      this.name = "ApiError";
    }
  },
}));

import { forgotPassword } from "@/api/auth";
import { apiFetchJson as mockApiFetchJson } from "@/api/client";
import { ApiContractError } from "@/api/contracts/common";

describe("forgotPassword contract (F1.1b)", () => {
  beforeEach(() => {
    vi.mocked(mockApiFetchJson).mockReset();
  });

  it("accepts a valid response with message", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValue({
      message: "Reset instructions sent.",
    });
    const result = await forgotPassword("user@example.com");
    expect(result.message).toBe("Reset instructions sent.");
  });

  it("accepts a valid response with optional reset_token", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValue({
      message: "Token generated.",
      reset_token: "abc123",
    });
    const result = await forgotPassword("user@example.com");
    expect(result.message).toBe("Token generated.");
    expect(result.reset_token).toBe("abc123");
  });

  it("rejects an HTTP error (ApiError propagates from transport)", async () => {
    const { ApiError } = await import("@/api/client");
    vi.mocked(mockApiFetchJson).mockRejectedValue(new ApiError(500, "Server error"));
    await expect(forgotPassword("user@example.com")).rejects.toThrow(/Server error/);
  });

  it("rejects a missing message field (ApiContractError)", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValue({ unrelated: "field" });
    await expect(forgotPassword("user@example.com")).rejects.toThrow(ApiContractError);
  });

  it("rejects a non-string message (ApiContractError)", async () => {
    vi.mocked(mockApiFetchJson).mockResolvedValue({ message: 42 });
    await expect(forgotPassword("user@example.com")).rejects.toThrow(ApiContractError);
  });
});
