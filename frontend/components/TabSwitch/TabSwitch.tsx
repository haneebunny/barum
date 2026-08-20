"use client";

import React from "react";

export interface TabOption<T> {
  value: T;
  label: string;
}

interface TabSwitchProps<T extends string | number> {
  label?: string;
  options: TabOption<T>[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}

export function TabSwitch<T extends string | number>({
  label,
  options,
  value,
  onChange,
  disabled = false,
}: TabSwitchProps<T>) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {label && (
        <span className="text-[var(--ink-3)] text-[11px] font-sans mr-0.5 select-none">
          {label}
        </span>
      )}
      <div className="flex items-center gap-1.5" role="group">
        {options.map((option) => {
          const isActive = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => !disabled && onChange(option.value)}
              disabled={disabled}
              className={`text-[11px] font-sans p-[4px_10px] border rounded-[2px] cursor-pointer transition-all duration-[120ms] select-none ${
                isActive
                  ? "border-[var(--brand-deep)] bg-[var(--nav-active-bg)] text-[var(--ink)] font-semibold"
                  : "border-[var(--line-2)] bg-transparent text-[var(--ink-3)] hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
              } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
