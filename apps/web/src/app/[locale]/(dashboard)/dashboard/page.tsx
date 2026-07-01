import { setRequestLocale, getTranslations } from "next-intl/server";
import { Card } from "@javobai/ui";
import { PageHeader } from "@/components/dashboard/page-header";
import { getCurrentUser } from "@/lib/api/server";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  const user = await getCurrentUser();

  return (
    <div>
      <PageHeader
        title={t("title")}
        subtitle={user ? t("welcome", { name: user.name ?? user.phone }) : undefined}
      />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-zinc-500">Kanallar</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-50">—</p>
        </Card>
        <Card>
          <p className="text-xs text-zinc-500">Bugungi suhbatlar</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-50">—</p>
        </Card>
        <Card>
          <p className="text-xs text-zinc-500">AI javob darajasi</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-50">—</p>
        </Card>
        <Card>
          <p className="text-xs text-zinc-500">Operatorga uzatilgan</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-50">—</p>
        </Card>
      </div>
      <p className="mt-6 text-sm text-zinc-500">{t("emptyState")}</p>
    </div>
  );
}
