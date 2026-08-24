"use client";

import React, { useRef, useState } from "react";
import { UploadSimple } from "@phosphor-icons/react";

export interface DropzoneProps {
  onFilesSelected: (files: FileList | File[]) => void;
  accept?: string;
  supportedExtensions?: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  multiple?: boolean;
  disabled?: boolean;
  compact?: boolean;
  className?: string;
  icon?: React.ReactNode;
}

export function Dropzone({
  onFilesSelected,
  accept = "image/png,image/jpeg,image/webp",
  supportedExtensions = "PNG · JPG · WEBP",
  title = "파일 던져넣기",
  subtitle = "drop or click · 여러 장 가능",
  multiple = true,
  disabled = false,
  compact = false,
  className = "",
  icon,
}: DropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (disabled) return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesSelected(e.dataTransfer.files);
    }
  };

  const handleClick = () => {
    if (disabled) return;
    fileInputRef.current?.click();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files);
      e.target.value = "";
    }
  };

  return (
    <div
      className={`border border-dashed transition-all duration-150 text-center select-none ${
        disabled
          ? "border-[var(--line)] bg-[var(--surface-sub)] opacity-50 cursor-not-allowed"
          : isDragging
          ? "border-[var(--brand)] bg-[var(--surface)] cursor-pointer"
          : "border-[var(--line-2)] bg-[var(--surface-sub)] hover:border-[var(--ink-3)] cursor-pointer"
      } ${compact ? "p-[12px_14px]" : "p-[16px_18px]"} ${className}`}
      onClick={handleClick}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label={typeof title === "string" ? title : "파일 첨부 영역"}
      onKeyDown={handleKeyDown}
    >
      <div className={`text-[var(--brand-ink)] flex justify-center ${compact ? "mb-1.5" : "mb-2"}`}>
        {icon || <UploadSimple size={compact ? 20 : 24} weight="regular" />}
      </div>

      <div className={`font-bold text-[var(--ink)] ${compact ? "text-[12.5px] mb-1" : "text-[13.5px] mb-1.5"}`}>
        {title}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-1.5">
        <span className="font-mono text-[10.5px] text-[var(--ink-3)]">
          {subtitle}
        </span>
        {supportedExtensions && (
          <span className="font-mono text-[10px] text-[var(--brand-ink)] bg-[var(--surface)] border border-[var(--line)] px-1.5 py-0.5 font-semibold">
            {supportedExtensions}
          </span>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        className="hidden"
        onChange={handleFileInputChange}
      />
    </div>
  );
}
