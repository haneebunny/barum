"use client";

import { useState, useRef, useEffect } from "react";
import { Dropdown } from "./Dropdown";

interface Option<T> {
  key: T;
  label: string;
}

interface FilterDropdownProps<T extends string | number> {
  label: string;
  options: readonly Option<T>[] | Option<T>[];
  selectedValue: T;
  onSelect: (value: T) => void;
  className?: string;
}

export function FilterDropdown<T extends string | number>({
  label,
  options,
  selectedValue,
  onSelect,
  className = "",
}: FilterDropdownProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => opt.key === selectedValue);
  const displayLabel = selectedOption ? selectedOption.label : String(selectedValue);

  // 버튼 토글 제어
  const handleToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsOpen((prev) => !prev);
  };

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (isOpen && containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [isOpen]);

  return (
    <div ref={containerRef} className={`relative inline-block text-left ${className}`}>
      <button
        type="button"
        onClick={handleToggle}
        className={`font-mono text-[11px] p-[5px_10px] border cursor-pointer transition-all duration-[120ms] inline-flex items-center gap-1.5 ${
          isOpen
            ? "border-[var(--ink-3)] text-[var(--ink)] bg-[var(--nav-active-bg)] font-bold"
            : "border-[var(--line-2)] text-[var(--ink-3)] bg-transparent hover:text-[var(--ink)] hover:border-[var(--ink-3)]"
        }`}
      >
        <span className="text-[var(--ink-3)]">{label}</span>
        <span className="text-[var(--ink)] font-bold">{displayLabel}</span>
        <svg
          className={`w-3 h-3 text-[var(--ink-3)] transition-transform duration-150 ${
            isOpen ? "rotate-180" : ""
          }`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="square"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <Dropdown isOpen={isOpen} onClose={() => setIsOpen(false)} className="left-0 right-auto mt-1 min-w-[120px]">
        {options.map((opt) => (
          <button
            key={String(opt.key)}
            type="button"
            className={`p-[8px_12px] text-left hover:bg-[var(--nav-hover)] transition-colors border-0 bg-transparent font-mono text-[11px] cursor-pointer w-full whitespace-nowrap ${
              opt.key === selectedValue
                ? "text-[var(--ink)] font-bold bg-[var(--nav-active-bg)]"
                : "text-[var(--ink-2)]"
            }`}
            onClick={() => {
              onSelect(opt.key);
              setIsOpen(false);
            }}
          >
            {opt.label}
          </button>
        ))}
      </Dropdown>
    </div>
  );
}
