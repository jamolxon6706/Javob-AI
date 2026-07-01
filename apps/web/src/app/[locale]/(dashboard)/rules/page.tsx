import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { RulesClient } from "@/components/rules/rules-client";

export default async function RulesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("rules");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <RulesClient />
    </div>
  );
}
