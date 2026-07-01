"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useLoginFlow } from "./use-login-flow";
import { PhoneStep } from "./phone-step";
import { OtpStep } from "./otp-step";

export function LoginFlow({ nextPath }: { nextPath: string | null }) {
  const t = useTranslations("auth");
  const router = useRouter();

  const flow = useLoginFlow({
    networkErrorMessage: t("errors.network"),
    invalidOtpMessage: t("errors.otpInvalid"),
  });

  async function handleVerify(otp: string) {
    const success = await flow.verify(otp);
    if (success) {
      router.replace(nextPath && nextPath.startsWith("/") ? nextPath : "/dashboard");
      router.refresh();
    }
  }

  return (
    <div className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900/60 p-6 shadow-xl shadow-black/20">
      {flow.step === "phone" ? (
        <PhoneStep
          onSubmit={flow.requestOtpFor}
          pending={flow.pending}
          serverError={flow.error}
        />
      ) : (
        <OtpStep
          phone={flow.phone}
          devOtp={flow.devOtp}
          onSubmit={handleVerify}
          onResend={flow.resend}
          onChangeNumber={flow.goBackToPhone}
          pending={flow.pending}
          serverError={flow.error}
        />
      )}
    </div>
  );
}
