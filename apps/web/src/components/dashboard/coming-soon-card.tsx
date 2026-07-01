import { useTranslations } from "next-intl";
import { Card } from "@javobai/ui";

export function ComingSoonCard() {
  const t = useTranslations("common");
  return (
    <Card className="flex h-48 items-center justify-center text-zinc-500">
      {t("comingSoon")}
    </Card>
  );
}
