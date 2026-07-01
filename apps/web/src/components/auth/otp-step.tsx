"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Input } from "@javobai/ui";
import { isValidOtp, maskPhone } from "@/lib/phone";

const RESEND_COOLDOWN_SECONDS = 30;

interface OtpStepProps {
  phone: string;
  devOtp: string | null;
  onSubmit: (otp: string) => Promise<void>;
  onResend: () => Promise<void>;
  onChangeNumber: () => void;
  pending: boolean;
  serverError: string | null;
}

export function OtpStep({
  phone,
  devOtp,
  onSubmit,
  onResend,
  onChangeNumber,
  pending,
  serverError,
}: OtpStepProps) {
  const t = useTranslations("auth");
  const [otp, setOtp] = useState("");
  const [touched, setTouched] = useState(false);
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);

  const valid = isValidOtp(otp);
  const showError = touched && !valid;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!valid) return;
    await onSubmit(otp.trim());
  }

  async function handleResend() {
    if (cooldown > 0) return;
    setCooldown(RESEND_COOLDOWN_SECONDS);
    await onResend();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-zinc-50">{t("otpTitle")}</h1>
        <p className="mt-1 text-sm text-zinc-400">
          {t("otpSubtitle", { phone: maskPhone(phone) })}
        </p>
      </div>

      {devOtp ? (
        <p className="rounded-md border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
          {t("devOtpHint", { otp: devOtp })}
        </p>
      ) : null}

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-zinc-300">{t("otpLabel")}</span>
        <Input
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          maxLength={6}
          placeholder={t("otpPlaceholder")}
          value={otp}
          onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
          onBlur={() => setTouched(true)}
          error={showError ? t("errors.otpRequired") : undefined}
        />
      </label>

      {serverError ? (
        <p className="text-sm text-red-400" role="alert">
          {serverError}
        </p>
      ) : null}

      <Button type="submit" disabled={pending || !valid}>
        {pending ? t("verify") + "…" : t("verify")}
      </Button>

      <div className="flex items-center justify-between text-sm">
        <button
          type="button"
          onClick={onChangeNumber}
          className="text-zinc-400 hover:text-zinc-200"
        >
          {t("changeNumber")}
        </button>
        <button
          type="button"
          onClick={handleResend}
          disabled={cooldown > 0}
          className="text-violet-400 hover:text-violet-300 disabled:text-zinc-500"
        >
          {cooldown > 0 ? t("resendIn", { seconds: cooldown }) : t("resend")}
        </button>
      </div>
    </form>
  );
}
