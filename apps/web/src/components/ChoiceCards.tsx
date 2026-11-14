import type { ReactNode } from "react";
import { cx } from "@/lib/format";

/** Radio group rendered as cards; native radios keep arrow-key navigation. */
export function ChoiceCards<T extends string>({
  name,
  legend,
  value,
  options,
  onChange,
  columns = 2,
}: {
  name: string;
  legend: ReactNode;
  value: T;
  options: Array<{ value: T; label: string; description?: ReactNode }>;
  onChange: (v: T) => void;
  columns?: 2 | 3 | 4;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div
        className={cx(
          "grid gap-2",
          columns === 2 && "sm:grid-cols-2",
          columns === 3 && "sm:grid-cols-3",
          columns === 4 && "sm:grid-cols-2 lg:grid-cols-4",
        )}
      >
        {options.map((o) => {
          const id = `${name}-${o.value}`;
          const checked = value === o.value;
          return (
            <label
              key={o.value}
              htmlFor={id}
              className={cx(
                "flex cursor-pointer gap-3 rounded-lg border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
                checked ? "border-accent bg-accent-soft" : "border-line bg-surface hover:bg-subtle",
              )}
            >
              <input
                id={id}
                type="radio"
                name={name}
                value={o.value}
                checked={checked}
                data-testid={id}
                onChange={() => onChange(o.value)}
                className="mt-0.5 accent-[var(--accent)]"
              />
              <span>
                <span className="block font-medium">{o.label}</span>
                {o.description && <span className="mt-0.5 block text-xs text-muted">{o.description}</span>}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
