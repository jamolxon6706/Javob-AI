"use client";

import { useTranslations } from "next-intl";

const NODE_TYPES = [
  {
    type: "message",
    icon: "💬",
    color: "bg-sky-500/10 text-sky-500 hover:bg-sky-500/20",
  },
  {
    type: "condition",
    icon: "🔀",
    color: "bg-amber-500/10 text-amber-500 hover:bg-amber-500/20",
  },
  {
    type: "action",
    icon: "⚡",
    color: "bg-violet-500/10 text-violet-500 hover:bg-violet-500/20",
  },
  {
    type: "wait",
    icon: "⏱",
    color: "bg-orange-500/10 text-orange-500 hover:bg-orange-500/20",
  },
  {
    type: "end",
    icon: "🏁",
    color: "bg-muted text-muted-foreground hover:bg-muted/80",
  },
];

interface Props {
  onAdd: (type: string) => void;
}

export default function NodePanel({ onAdd }: Props) {
  const t = useTranslations("flows.nodes");

  return (
    <div className="w-48 border-r bg-card p-3 flex flex-col gap-1.5 overflow-y-auto">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 px-1">
        {t("panel_title")}
      </p>
      {NODE_TYPES.map((n) => (
        <button
          key={n.type}
          onClick={() => onAdd(n.type)}
          draggable
          className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition cursor-pointer ${n.color}`}
        >
          <span className="text-base">{n.icon}</span>
          <span>{t(n.type)}</span>
        </button>
      ))}

      <div className="mt-4 pt-4 border-t">
        <p className="text-xs text-muted-foreground px-1 mb-2">Eslatma</p>
        <p className="text-xs text-muted-foreground px-1 leading-relaxed">
          Tugunni kanvaga qo'shish uchun bosing. Chiziq tortish uchun tugun
          chetidagi doirachani suring.
        </p>
      </div>
    </div>
  );
}
