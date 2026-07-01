import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export function Input({ error, className = "", ...props }: InputProps) {
  const base =
    "w-full rounded-lg border bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-600 disabled:opacity-50";
  const border = error ? "border-red-500" : "border-zinc-700";

  return (
    <div className="flex flex-col gap-1">
      <input className={`${base} ${border} ${className}`} {...props} />
      {error ? <span className="text-xs text-red-400">{error}</span> : null}
    </div>
  );
}
