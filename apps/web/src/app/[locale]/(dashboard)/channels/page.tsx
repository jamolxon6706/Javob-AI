import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { ChannelsPageClient } from "@/components/channels/channels-page-client";

export default async function ChannelsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("channels");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <ChannelsPageClient />
    </div>
  );
}
