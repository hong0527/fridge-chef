import Link from 'next/link';
import { ArrowRight, Refrigerator, Sparkles, ChefHat } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { FridgeChip } from '@/components/FridgeChip';

/**
 * 홈 — 랜딩 (SRS v1.10).
 * 디자인: 두꺼운 손그림 보더 + 잡지 헤드라인 톤의 한글 디스플레이 + 듀얼 모델 미리보기 카드.
 */
export default function HomePage() {
  return (
    <main className="min-h-screen relative overflow-hidden bg-cream-100 dark:bg-clay-900">
      <header className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 py-6 flex items-center justify-between">
        <BrandLockup size="md" href={null} />
        <nav className="flex items-center gap-2">
          <Link
            href="/auth?mode=login"
            className="hidden sm:inline-flex items-center px-4 h-10 rounded-full font-semibold text-clay-900 dark:text-cream-100 hover:bg-cream-200 dark:hover:bg-clay-800 transition-colors"
          >
            로그인
          </Link>
          <Link
            href="/auth?mode=signup"
            className="inline-flex items-center gap-1.5 px-5 h-10 rounded-full font-semibold bg-clay-900 text-cream-50 border-2 border-clay-900 hover:bg-gochu-500 dark:bg-cream-100 dark:text-clay-900 dark:border-cream-100 dark:hover:bg-gochu-500 dark:hover:text-cream-50 transition-colors"
          >
            시작하기
            <ArrowRight className="h-4 w-4" />
          </Link>
        </nav>
      </header>

      <section className="relative max-w-7xl mx-auto px-6 lg:px-12 pt-8 sm:pt-16 pb-24">
        <span
          aria-hidden="true"
          className="absolute top-10 -left-12 h-72 w-72 rounded-full bg-mustard-400/40 blur-3xl"
        />
        <span
          aria-hidden="true"
          className="absolute -bottom-20 right-0 h-80 w-80 rounded-full bg-gochu-500/25 blur-3xl"
        />

        <div className="relative grid lg:grid-cols-12 gap-10 lg:gap-16 items-center stagger">
          <div className="lg:col-span-7">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cream-50 dark:bg-clay-800 border-2 border-clay-900 dark:border-cream-100 text-xs font-bold tracking-widest uppercase">
              <Sparkles className="h-3.5 w-3.5 text-gochu-500" aria-hidden="true" />
              AI 듀얼 추천 · 모델 A + 모델 B
            </span>
            <h1 className="mt-6 font-display font-bold leading-[1.05] tracking-tight text-[44px] sm:text-6xl lg:text-7xl">
              냉장고 재료로<br />
              <span className="ink-underline">오늘 뭐 먹지?</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg sm:text-xl text-clay-700 dark:text-cream-200 leading-relaxed">
              남은 재료만 입력하면, AI가 <strong>냉털 레시피 10개</strong>와<br className="hidden sm:block" />
              <strong>딱 한 가지만 더 사면 되는 레시피 3개</strong>를 한 번에 골라드려요.
            </p>

            <div className="mt-10 flex flex-wrap items-center gap-3">
              <Link
                href="/auth?mode=signup"
                className="inline-flex items-center gap-2 h-14 px-8 rounded-full bg-gochu-500 text-cream-50 border-2 border-clay-900 dark:border-cream-100 font-bold text-lg shadow-sticker hover:shadow-sticker-hover hover:-translate-y-0.5 transition-all"
              >
                무료로 시작하기
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="/auth?mode=login"
                className="inline-flex items-center gap-2 h-14 px-8 rounded-full bg-cream-50 dark:bg-clay-800 text-clay-900 dark:text-cream-100 border-2 border-clay-900 dark:border-cream-100 font-bold text-lg shadow-sticker hover:shadow-sticker-hover hover:-translate-y-0.5 transition-all"
              >
                로그인
              </Link>
            </div>

            <ul className="mt-10 grid grid-cols-2 gap-x-6 gap-y-3 max-w-md text-sm text-clay-700 dark:text-cream-200">
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-herb-500" /> 동의어 자동 인식
              </li>
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-mustard-500" /> 알레르기 자동 제외
              </li>
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-gochu-500" /> 맵기 0~9 조절
              </li>
              <li className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-clay-900 dark:bg-cream-100" /> Gemini 추천 이유
              </li>
            </ul>
          </div>

          <div className="lg:col-span-5">
            <div className="relative">
              <div className="relative rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 p-6 shadow-sticker rotate-[-2deg]">
                <span className="absolute -top-3 left-5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-herb-500 text-cream-50 border-2 border-clay-900 text-xs font-bold">
                  <Refrigerator className="h-3.5 w-3.5" aria-hidden="true" />
                  모델 A · 냉털 10개
                </span>
                <h3 className="mt-2 font-display text-xl font-bold">애호박 새우젓 볶음</h3>
                <p className="text-sm text-clay-600 dark:text-clay-400">12분 · 초보 · 1인분</p>
                <p className="mt-3 text-[11px] font-bold tracking-wider uppercase text-herb-600 dark:text-herb-400">
                  활용할 냉장고 재료
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <FridgeChip name="애호박" variant="used" />
                  <FridgeChip name="대파" variant="used" />
                  <FridgeChip name="마늘" variant="used" />
                  <FridgeChip name="새우젓" variant="used" />
                </div>
              </div>

              <div className="relative rounded-3xl border-2 border-mustard-500 bg-cream-50 dark:bg-clay-800 p-6 shadow-sticker mt-5 rotate-[1.5deg] ml-6">
                <span className="absolute -top-3 left-5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-mustard-500 text-clay-900 border-2 border-clay-900 text-xs font-bold">
                  <ChefHat className="h-3.5 w-3.5" aria-hidden="true" />
                  모델 B · 부족재료 3개
                </span>
                <h3 className="mt-2 font-display text-xl font-bold">토마토 달걀 볶음밥</h3>
                <p className="text-sm text-clay-600 dark:text-clay-400">15분 · 왕초보 · 2인분</p>
                <p className="mt-3 text-[11px] font-bold tracking-wider uppercase text-mustard-600 dark:text-mustard-400">
                  이것만 있으면 돼요
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <FridgeChip name="토마토" variant="missing" />
                </div>
                <div className="mt-3 rounded-2xl border-2 border-dashed border-mustard-500/40 bg-mustard-500/5 px-3 py-2 text-xs text-clay-700 dark:text-cream-200">
                  <span className="font-bold text-mustard-600 dark:text-mustard-400">Gemini </span>
                  &ldquo;냉장고에 달걀과 밥이 있어, 토마토만 추가하면 단 한 끼로 완성!&rdquo;
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="relative z-10 max-w-7xl mx-auto px-6 lg:px-12 py-8 border-t-2 border-clay-900/10 dark:border-cream-100/10 text-sm text-clay-600 dark:text-clay-400 flex flex-wrap items-center justify-between gap-3">
        <p>© 2026 냉장고 셰프 — SRS v1.10 데모</p>
        <p>WCAG AA · Pretendard · Gmarket Sans</p>
      </footer>
    </main>
  );
}
