import { redirect } from "@/i18n/navigation";
import { setRequestLocale } from "next-intl/server";

export default async function LocaleIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  redirect({ href: "/dashboard", locale });
}
