import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { CampaignsClient } from "@/components/campaigns/campaigns-client";

export default async function CampaignsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("campaigns");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <CampaignsClient />
    </div>
  );
}
