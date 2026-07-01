import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { ComingSoonCard } from "@/components/dashboard/coming-soon-card";

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("analytics");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <ComingSoonCard />
    </div>
  );
}
