import Link from 'next/link';
import { cn } from '@/lib/cn';

/**
 * 냉장고 셰프 로고 — 손그림 톤의 SVG 마크 + 워드마크.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      aria-hidden="true"
      className={cn('block', className)}
    >
      {/* fridge body */}
      <rect
        x="9"
        y="4"
        width="30"
        height="40"
        rx="6"
        fill="#FAF7F2"
        stroke="#1A1715"
        strokeWidth="2.4"
      />
      {/* divider */}
      <line x1="9" y1="19" x2="39" y2="19" stroke="#1A1715" strokeWidth="2.4" />
      {/* handles */}
      <rect x="13" y="11" width="2.4" height="5" rx="1" fill="#1A1715" />
      <rect x="13" y="24" width="2.4" height="7" rx="1" fill="#1A1715" />
      {/* chef hat */}
      <path
        d="M19 9c0-3 2.6-5 5-5s5 2 5 5"
        stroke="#E2553D"
        strokeWidth="2.4"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="24" cy="9" r="1.6" fill="#E2553D" />
      {/* sparkle */}
      <path
        d="M33 28l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"
        fill="#E8A33D"
      />
    </svg>
  );
}

export function BrandLockup({
  size = 'md',
  href = '/',
}: {
  size?: 'sm' | 'md' | 'lg';
  href?: string | null;
}) {
  const sizes = {
    sm: { mark: 'h-7 w-7', text: 'text-base' },
    md: { mark: 'h-9 w-9', text: 'text-xl' },
    lg: { mark: 'h-14 w-14', text: 'text-3xl' },
  } as const;
  const inner = (
    <span className="inline-flex items-center gap-2.5">
      <BrandMark className={sizes[size].mark} />
      <span
        className={cn(
          'font-display font-bold tracking-tight',
          sizes[size].text,
        )}
      >
        냉장고<span className="text-gochu-500">셰프</span>
      </span>
    </span>
  );
  if (!href) return inner;
  return (
    <Link
      href={href}
      aria-label="냉장고 셰프 홈으로"
      className="inline-block focus:outline-none"
    >
      {inner}
    </Link>
  );
}
