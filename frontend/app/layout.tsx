import type { Metadata, Viewport } from 'next';
import './globals.css';
import { ToastProvider } from '@/components/Toast';

export const metadata: Metadata = {
  title: '냉장고 셰프 — 오늘 뭐 먹지?',
  description:
    '냉장고에 있는 재료로 오늘 메뉴를 추천해드립니다. 냉털 레시피 10개와 부족 재료 보충 레시피 3개를 동시에 제안하는 AI 추천 서비스.',
  keywords: ['냉장고 레시피', '냉털 요리', '오늘 뭐 먹지', '레시피 추천', 'AI 요리'],
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#FAF7F2' },
    { media: '(prefers-color-scheme: dark)', color: '#1A1715' },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen antialiased">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
