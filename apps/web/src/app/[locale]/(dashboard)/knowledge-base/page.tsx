import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { KnowledgeBaseClient } from "@/components/knowledge-base/knowledge-base-client";

export default async function KnowledgeBasePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("knowledgeBase");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <KnowledgeBaseClient />
    </div>
  );
}
