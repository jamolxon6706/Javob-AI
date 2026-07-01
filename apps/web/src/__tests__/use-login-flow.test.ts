import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useLoginFlow } from "@/components/auth/use-login-flow";

const OPTIONS = {
  networkErrorMessage: "Network error",
  invalidOtpMessage: "Invalid code",
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useLoginFlow", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts on the phone step", () => {
    const { result } = renderHook(() => useLoginFlow(OPTIONS));
    expect(result.current.step).toBe("phone");
    expect(result.current.pending).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("moves to the otp step after a successful request-otp call", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "sent", otp: "123456" })
    );

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });

    expect(result.current.step).toBe("otp");
    expect(result.current.phone).toBe("+998901234567");
    expect(result.current.devOtp).toBe("123456");
    expect(result.current.error).toBeNull();
  });

  it("surfaces the server's error detail when request-otp fails", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({ detail: "Too many requests" }, 429)
    );

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });

    expect(result.current.step).toBe("phone");
    expect(result.current.error).toBe("Too many requests");
  });

  it("falls back to the network error message when fetch throws", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("fetch failed"));

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });

    expect(result.current.error).toBe(OPTIONS.networkErrorMessage);
  });

  it("returns true from verify() on success", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: "sent", otp: "123456" }))
      .mockResolvedValueOnce(
        jsonResponse({
          access_token: "a",
          refresh_token: "b",
          token_type: "bearer",
        })
      );

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });

    let success = false;
    await act(async () => {
      success = await result.current.verify("123456");
    });

    expect(success).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("maps a 400 verify response to the invalid-otp message", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: "sent" }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Bad code" }, 400));

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });

    let success = true;
    await act(async () => {
      success = await result.current.verify("000000");
    });

    expect(success).toBe(false);
    expect(result.current.error).toBe(OPTIONS.invalidOtpMessage);
  });

  it("goBackToPhone resets to the phone step and clears errors", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: "sent" }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Bad code" }, 400));

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });
    await act(async () => {
      await result.current.verify("000000");
    });
    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.goBackToPhone();
    });

    expect(result.current.step).toBe("phone");
    expect(result.current.error).toBeNull();
  });

  it("resend re-requests an OTP for the already-confirmed phone", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ detail: "sent", otp: "111111" }))
      .mockResolvedValueOnce(jsonResponse({ detail: "sent", otp: "222222" }));

    const { result } = renderHook(() => useLoginFlow(OPTIONS));

    await act(async () => {
      await result.current.requestOtpFor("+998901234567");
    });
    expect(result.current.devOtp).toBe("111111");

    await act(async () => {
      await result.current.resend();
    });
    expect(result.current.devOtp).toBe("222222");

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  });
});
