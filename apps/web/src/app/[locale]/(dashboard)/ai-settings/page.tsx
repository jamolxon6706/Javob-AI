import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { AISettingsClient } from "@/components/ai-settings/ai-settings-client";

export default async function AiSettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("aiSettings");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <AISettingsClient />
    </div>
  );
}
