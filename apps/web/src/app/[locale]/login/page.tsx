import { setRequestLocale } from "next-intl/server";
import { LoginFlow } from "@/components/auth/login-flow";

export default async function LoginPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const { next } = await searchParams;

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-16">
      <LoginFlow nextPath={next ?? null} />
    </div>
  );
}
