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
      <header className="relative z-10 max-w-screen-2xl mx-auto px-6 lg:px-12 py-8 flex items-center justify-between">
        <BrandLockup size="lg" href={null} />
        <nav className="flex items-center gap-4">
          <Link
            href="/auth?mode=login"
            className="hidden sm:inline-flex items-center px-6 h-12 rounded-full font-semibold text-clay-900 dark:text-cream-100 hover:bg-cream-200 dark:hover:bg-clay-800 transition-colors"
          >
            로그인
          </Link>
          <Link
            href="/auth?mode=signup"
            className="inline-flex items-center gap-2 px-6 h-12 rounded-full font-semibold bg-clay-900 text-cream-50 border border-clay-900/10 hover:bg-gochu-500 dark:bg-cream-100 dark:text-clay-900 dark:border-cream-100 dark:hover:bg-gochu-500 dark:hover:text-cream-50 transition-colors shadow-soft"
          >
            시작하기
            <ArrowRight className="h-5 w-5" />
          </Link>
        </nav>
      </header>

      <section className="relative max-w-screen-2xl mx-auto px-6 lg:px-12 py-16 sm:py-24 lg:py-32 min-h-[calc(100vh-180px)] flex flex-col justify-center">
        <span
          aria-hidden="true"
          className="absolute top-20 -left-12 h-96 w-96 rounded-full bg-mustard-400/30 blur-[100px]"
        />
        <span
          aria-hidden="true"
          className="absolute bottom-20 right-0 h-96 w-96 rounded-full bg-gochu-500/20 blur-[100px]"
        />

        <div className="relative grid lg:grid-cols-12 gap-12 lg:gap-16 items-center stagger">
          <div className="lg:col-span-7">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-cream-50 dark:bg-clay-800 border border-clay-900/10 dark:border-cream-100/10 text-xs font-bold tracking-widest uppercase shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-gochu-500" aria-hidden="true" />
              AI 듀얼 추천 · 모델 A + 모델 B
            </span>
            <h1 className="mt-8 font-display font-bold leading-[1.05] tracking-tight text-[52px] sm:text-7xl lg:text-8xl">
              냉장고 재료로<br />
              <span className="ink-underline">오늘 뭐 먹지?</span>
            </h1>
            <p className="mt-8 max-w-xl text-xl sm:text-2xl text-clay-700 dark:text-cream-200 leading-relaxed opacity-90">
              남은 재료만 입력하면, AI가 <strong>냉털 레시피 10개</strong>와<br className="hidden sm:block" />
              <strong>딱 한 가지만 더 사면 되는 레시피 3개</strong>를 한 번에 골라드려요.
            </p>

            <div className="mt-12 flex flex-wrap items-center gap-4">
              <Link
                href="/auth?mode=signup"
                className="inline-flex items-center gap-2 h-16 px-10 rounded-full bg-gochu-500 text-cream-50 border border-clay-900/10 dark:border-cream-100/10 font-bold text-xl shadow-soft hover:shadow-lg hover:-translate-y-1 transition-all"
              >
                무료로 시작하기
                <ArrowRight className="h-6 w-6" />
              </Link>
              <Link
                href="/auth?mode=login"
                className="inline-flex items-center gap-2 h-16 px-10 rounded-full bg-cream-50 dark:bg-clay-800 text-clay-900 dark:text-cream-100 border border-clay-900/10 dark:border-cream-100/10 font-bold text-xl shadow-soft hover:shadow-lg hover:-translate-y-1 transition-all"
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

          <div className="lg:col-span-5 lg:pl-10">
            <div className="relative scale-110 origin-center">
              <div className="relative rounded-[32px] border border-clay-900/10 dark:border-cream-100/10 bg-cream-50 dark:bg-clay-800 p-8 shadow-soft rotate-[-2deg] hover:rotate-0 transition-transform duration-500">
                <span className="absolute -top-3 left-6 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-herb-500 text-cream-50 shadow-sm text-xs font-bold">
                  <Refrigerator className="h-3.5 w-3.5" aria-hidden="true" />
                  모델 A · 냉털 10개
                </span>
                <h3 className="mt-3 font-display text-2xl font-bold">애호박 새우젓 볶음</h3>
                <p className="text-sm text-clay-500 dark:text-clay-400">12분 · 초보 · 1인분</p>
                <p className="mt-5 text-[11px] font-bold tracking-wider uppercase text-herb-600 dark:text-herb-400">
                  활용할 냉장고 재료
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <FridgeChip name="애호박" variant="used" />
                  <FridgeChip name="대파" variant="used" />
                  <FridgeChip name="마늘" variant="used" />
                  <FridgeChip name="새우젓" variant="used" />
                </div>
              </div>

              <div className="relative rounded-[32px] border border-mustard-500/20 bg-cream-50 dark:bg-clay-800 p-8 shadow-soft mt-8 rotate-[2deg] ml-8 hover:rotate-0 transition-transform duration-500">
                <span className="absolute -top-3 left-6 inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-mustard-500 text-clay-900 shadow-sm text-xs font-bold">
                  <ChefHat className="h-3.5 w-3.5" aria-hidden="true" />
                  모델 B · 부족재료 3개
                </span>
                <h3 className="mt-3 font-display text-2xl font-bold">토마토 달걀 볶음밥</h3>
                <p className="text-sm text-clay-500 dark:text-clay-400">15분 · 왕초보 · 2인분</p>
                <p className="mt-5 text-[11px] font-bold tracking-wider uppercase text-mustard-600 dark:text-mustard-400">
                  이것만 있으면 돼요
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <FridgeChip name="토마토" variant="missing" />
                </div>
                <div className="mt-4 rounded-2xl border border-dashed border-mustard-500/30 bg-mustard-500/5 px-4 py-3 text-sm text-clay-700 dark:text-cream-100 leading-snug">
                  <span className="font-bold text-mustard-600 dark:text-mustard-400">Gemini </span>
                  &ldquo;냉장고에 달걀과 밥이 있어, 토마토만 추가하면 완벽한 한 끼가 돼요!&rdquo;
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="relative z-10 max-w-screen-2xl mx-auto px-6 lg:px-12 py-10 border-t border-clay-900/10 dark:border-cream-100/10 text-sm text-clay-500 dark:text-clay-400 flex flex-wrap items-center justify-between gap-6">
        <p>© 2026 냉장고 셰프 — SRS v1.10 데모</p>
        <p>WCAG AA · Pretendard · Gmarket Sans</p>
      </footer>
    </main>
  );
}
