'use client';

import { X } from 'lucide-react';
import { cn } from '@/lib/cn';

interface FridgeChipProps {
  name: string;
  onRemove?: () => void;
  onEdit?: () => void;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  variant?: 'default' | 'used' | 'missing' | 'compact';
  categoryColor?: 'vegetable' | 'legume' | 'grain' | 'meat' | 'seafood' | 'dairy' | 'seasoning';
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
  onEdit,
  selectable,
  selected,
  onSelect,
  variant = 'default',
  categoryColor,
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

  // NFR-USE-001 — 카테고리 색상으로 재료 식품군을 시각적으로 즉시 구분
  // RF-07: categoryColor 지정 시 밝은 배경과 어두운 그림자 불일치 방지
  const categoryStyles = {
    vegetable: 'border-green-600  bg-green-50  dark:bg-green-950/30  text-green-800  dark:text-green-300',
    legume:    'border-purple-500 bg-purple-50 dark:bg-purple-950/30 text-purple-800 dark:text-purple-300',
    grain:     'border-amber-700  bg-amber-100 dark:bg-amber-900/40   text-amber-900  dark:text-amber-200',
    meat:      'border-red-500    bg-red-50    dark:bg-red-950/30    text-red-800    dark:text-red-300',
    seafood:   'border-blue-500   bg-blue-50   dark:bg-blue-950/30   text-blue-800   dark:text-blue-300',
    dairy:     'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-800 dark:text-yellow-300',
    seasoning: 'border-orange-400 bg-orange-50 dark:bg-orange-950/30 text-orange-700 dark:text-orange-300',
  } as const;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-chip border-2 font-medium text-sm whitespace-nowrap',
        'transition-transform duration-150 hover:-translate-y-0.5',
        variant !== 'compact' && !categoryColor && 'shadow-[0_2px_0_0_rgba(26,23,21,0.85)]',
        categoryColor ? categoryStyles[categoryColor] : styles[variant],
        selected && 'border-gochu-500 ring-2 ring-gochu-500/40',
        selectable && 'cursor-pointer',
        className,
      )}
      style={{ wordBreak: 'keep-all' }}
      onClick={selectable ? onSelect : undefined}
    >
      <span
        className={cn('leading-none', onEdit && 'cursor-pointer hover:underline underline-offset-2')}
        onClick={onEdit}
        title={onEdit ? '클릭해서 편집' : undefined}
      >
        {name}
      </span>
      {selectable ? (
        <span
          className={cn(
            'inline-flex h-4 w-4 items-center justify-center rounded border-2 transition-colors',
            selected ? 'bg-gochu-500 border-gochu-500 text-white' : 'border-clay-400',
          )}
        >
          {selected && <span className="text-[10px] leading-none">✓</span>}
        </span>
      ) : onRemove && (
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
