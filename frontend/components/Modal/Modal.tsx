"use client";

import React, { useEffect, useImperativeHandle, useRef } from "react";

interface ModalProps {
  isOpen: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md";
}

export const Modal = React.forwardRef<HTMLButtonElement, ModalProps>(
  ({ isOpen, title, onClose, children, footer, size = "sm" }, ref) => {
    const closeBtnRef = useRef<HTMLButtonElement>(null);

    // Forward the ref to closeBtnRef
    useImperativeHandle(ref, () => closeBtnRef.current!);

    useEffect(() => {
      if (isOpen) {
        closeBtnRef.current?.focus();
      }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    };

    return (
      <div
        className="modal-backdrop"
        onClick={handleBackdropClick}
      >
        <div
          className={`modal ${size === "md" ? "modal-md" : "modal-sm"}`}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-head">
            <span>[ {title} ]</span>
            <button
              className="modal-x"
              ref={closeBtnRef}
              aria-label="닫기"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
          <div className="modal-body">
            {children}
          </div>
          {footer && (
            <div className="modal-foot">
              {footer}
            </div>
          )}
        </div>
      </div>
    );
  }
);

Modal.displayName = "Modal";
