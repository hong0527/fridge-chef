'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const base =
  'relative inline-flex items-center justify-center gap-2 font-semibold tracking-tight rounded-full transition-all duration-200 select-none disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-[1px]';

const variants: Record<Variant, string> = {
  primary:
    'bg-gochu-500 text-cream-50 border-2 border-clay-900 shadow-sticker hover:shadow-sticker-hover hover:-translate-y-0.5 dark:border-cream-100',
  secondary:
    'bg-cream-50 text-clay-900 border-2 border-clay-900 shadow-sticker hover:shadow-sticker-hover hover:-translate-y-0.5 dark:bg-clay-800 dark:text-cream-100 dark:border-cream-100',
  ghost:
    'bg-transparent text-clay-900 hover:bg-cream-200 dark:text-cream-100 dark:hover:bg-clay-700',
  danger:
    'bg-clay-900 text-cream-50 border-2 border-clay-900 hover:bg-gochu-700',
};

const sizes: Record<Size, string> = {
  sm: 'h-9 px-4 text-sm',
  md: 'h-11 px-6 text-base',
  lg: 'h-14 px-8 text-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      loading = false,
      disabled,
      children,
      ...rest
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(base, variants[variant], sizes[size], className)}
        {...rest}
      >
        {loading && (
          <span
            aria-hidden="true"
            className="inline-block h-4 w-4 rounded-full border-2 border-current border-r-transparent animate-spin"
          />
        )}
        <span className={cn(loading && 'opacity-90')}>{children}</span>
      </button>
    );
  },
);
Button.displayName = 'Button';
