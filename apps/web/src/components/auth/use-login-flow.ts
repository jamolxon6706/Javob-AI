import { useState } from "react";
import { ApiError, requestOtp, verifyOtp } from "@/lib/api/auth";

export type LoginStep = "phone" | "otp";

export interface UseLoginFlowResult {
  step: LoginStep;
  phone: string;
  devOtp: string | null;
  pending: boolean;
  error: string | null;
  requestOtpFor: (normalizedPhone: string) => Promise<void>;
  verify: (otp: string) => Promise<boolean>;
  resend: () => Promise<void>;
  goBackToPhone: () => void;
}

interface UseLoginFlowOptions {
  /** Translated fallback messages, since this hook has no i18n context. */
  networkErrorMessage: string;
  invalidOtpMessage: string;
}

/**
 * Encapsulates the phone -> request-otp -> verify state machine. Kept free
 * of `next/navigation` so it can be unit tested without an App Router test
 * harness; the LoginFlow component owns the actual redirect-on-success.
 */
export function useLoginFlow({
  networkErrorMessage,
  invalidOtpMessage,
}: UseLoginFlowOptions): UseLoginFlowResult {
  const [step, setStep] = useState<LoginStep>("phone");
  const [phone, setPhone] = useState("");
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function requestOtpFor(normalizedPhone: string) {
    setPending(true);
    setError(null);
    try {
      const result = await requestOtp(normalizedPhone);
      setPhone(normalizedPhone);
      setDevOtp(result.otp ?? null);
      setStep("otp");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : networkErrorMessage);
    } finally {
      setPending(false);
    }
  }

  /** Returns true on success (caller is responsible for redirecting). */
  async function verify(otp: string): Promise<boolean> {
    setPending(true);
    setError(null);
    try {
      await verifyOtp({ phone, otp });
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        setError(invalidOtpMessage);
      } else {
        setError(err instanceof ApiError ? err.detail : networkErrorMessage);
      }
      return false;
    } finally {
      setPending(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      const result = await requestOtp(phone);
      setDevOtp(result.otp ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : networkErrorMessage);
    }
  }

  function goBackToPhone() {
    setStep("phone");
    setError(null);
  }

  return { step, phone, devOtp, pending, error, requestOtpFor, verify, resend, goBackToPhone };
}
