"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button, Input } from "@javobai/ui";
import { isValidUzPhone, normalizeUzPhone } from "@/lib/phone";

interface PhoneStepProps {
  onSubmit: (phone: string) => Promise<void>;
  pending: boolean;
  serverError: string | null;
}

export function PhoneStep({ onSubmit, pending, serverError }: PhoneStepProps) {
  const t = useTranslations("auth");
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  const normalized = normalizeUzPhone(value);
  const valid = isValidUzPhone(value);
  const showError = touched && !valid;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!normalized) return;
    await onSubmit(normalized);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-zinc-50">{t("loginTitle")}</h1>
        <p className="mt-1 text-sm text-zinc-400">{t("loginSubtitle")}</p>
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-zinc-300">{t("phoneLabel")}</span>
        <Input
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          autoFocus
          placeholder={t("phonePlaceholder")}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => setTouched(true)}
          error={showError ? t("errors.invalidPhone") : undefined}
        />
      </label>

      {serverError ? (
        <p className="text-sm text-red-400" role="alert">
          {serverError}
        </p>
      ) : null}

      <Button type="submit" disabled={pending || !valid}>
        {pending ? t("sendOtp") + "…" : t("sendOtp")}
      </Button>
    </form>
  );
}
