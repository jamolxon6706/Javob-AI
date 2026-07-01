import { setRequestLocale, getTranslations } from "next-intl/server";
import { PageHeader } from "@/components/dashboard/page-header";
import { InboxClient } from "@/components/inbox/inbox-client";

export default async function InboxPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("inbox");

  return (
    <div>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <InboxClient />
    </div>
  );
}
