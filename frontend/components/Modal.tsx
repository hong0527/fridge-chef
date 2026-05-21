'use client';

import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  labelledBy?: string;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  labelledBy,
}: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-clay-900/40 backdrop-blur-sm px-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
          role="dialog"
          aria-modal="true"
          aria-labelledby={labelledBy ?? 'modal-title'}
        >
          <motion.div
            ref={ref}
            initial={{ y: 32, scale: 0.96, opacity: 0 }}
            animate={{ y: 0, scale: 1, opacity: 1 }}
            exit={{ y: 16, scale: 0.98, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full sm:max-w-md bg-cream-50 dark:bg-clay-800 rounded-3xl border-2 border-clay-900 dark:border-cream-100 shadow-sticker p-6 sm:p-8"
          >
            {title && (
              <h2
                id={labelledBy ?? 'modal-title'}
                className="font-display text-2xl font-bold mb-3 pr-8"
              >
                {title}
              </h2>
            )}
            <button
              onClick={onClose}
              aria-label="닫기"
              className="absolute top-4 right-4 h-9 w-9 inline-flex items-center justify-center rounded-full hover:bg-cream-200 dark:hover:bg-clay-700"
            >
              <X className="h-5 w-5" />
            </button>
            <div>{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
