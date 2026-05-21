'use client';

import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  variant?: 'default' | 'used' | 'missing' | 'compact';
  className?: string;
}

/**
 * 재료 태그 — 한글 한 글자 깨짐 방지(word-break: keep-all + min-w 보장).
 * 변형:
 *  - default: 냉장고 화면 입력 태그
 *  - used:    모델 A "활용할 냉장고 재료"
 *  - missing: 모델 B "이것만 있으면 돼요"
 *  - compact: 좁은 영역
 */
export function FridgeChip({
  name,
  onRemove,
  variant = 'default',
  className,
}: FridgeChipProps) {
  const styles = {
    default:
      'bg-cream-50 dark:bg-clay-800 text-clay-900 dark:text-cream-100 border-clay-900 dark:border-cream-100',
    used: 'bg-herb-500/15 text-herb-600 dark:text-herb-400 border-herb-500',
    missing:
      'bg-mustard-500/20 text-mustard-600 dark:text-mustard-400 border-mustard-500',
    compact:
      'bg-cream-200 dark:bg-clay-700 text-clay-900 dark:text-cream-100 border-transparent',
  } as const;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
        'transition-transform duration-150 hover:-translate-y-0.5',
        variant !== 'compact' && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
        styles[variant],
        className,
      )}
      style={{ wordBreak: 'keep-all' }}
    >
      <span className="leading-none">{name}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`${name} 재료 삭제`}
          className="inline-flex h-5 w-5 items-center justify-center rounded-full hover:bg-clay-900/10 dark:hover:bg-cream-100/15"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </span>
  );
}
