import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ToastProvider } from '@/components/Toast';
import FavoritesPage from '@/app/(main)/favorites/page';
import * as api from '@/lib/api';

// next/navigation mock
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
}));

// framer-motion mock (motion.div 렌더링 처리)
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<React.HTMLAttributes<HTMLDivElement>>) =>
      React.createElement('div', props, children),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) =>
    React.createElement(React.Fragment, null, children),
}));

// api mock
jest.mock('@/lib/api', () => ({
  getFavorites: jest.fn(),
  removeFavorite: jest.fn(),
  apiErrorMessage: jest.fn((err: unknown) => (err instanceof Error ? err.message : '오류')),
}));

const mockFavorites = {
  items: [
    {
      recipe_id: 'r001',
      name: '김치찌개',
      cook_min: 30,
      spicy: 3,
      difficulty_level: 2,
      country: 'kr',
      theme: 'soup',
      favorited_at: '2026-01-01T00:00:00Z',
    },
    {
      recipe_id: 'r002',
      name: '된장찌개',
      cook_min: 20,
      spicy: 1,
      difficulty_level: 1,
      country: 'kr',
      theme: 'soup',
      favorited_at: '2026-01-02T00:00:00Z',
    },
  ],
  total: 2,
};

function renderPage() {
  return render(
    <ToastProvider>
      <FavoritesPage />
    </ToastProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  (api.getFavorites as jest.Mock).mockResolvedValue(mockFavorites);
  (api.removeFavorite as jest.Mock).mockResolvedValue(undefined);
});

describe('FavoritesPage (FV-001~005)', () => {
  it('FV-001: 즐겨찾기 목록 2건 조회 시 레시피 카드 2개가 화면에 표시된다', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('김치찌개')).toBeInTheDocument();
      expect(screen.getByText('된장찌개')).toBeInTheDocument();
    });
  });

  it('FV-002: 즐겨찾기 목록이 비어있을 때 빈 상태 메시지가 표시된다', async () => {
    (api.getFavorites as jest.Mock).mockResolvedValue({ items: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/즐겨찾기한 레시피가 없어요/)).toBeInTheDocument();
    });
  });

  it('FV-003: 삭제 버튼 클릭 시 removeFavorite API가 호출된다', async () => {
    renderPage();
    const removeButtons = await screen.findAllByRole('button', { name: /즐겨찾기 해제/ });

    fireEvent.click(removeButtons[0]);
    await waitFor(() => {
      expect(api.removeFavorite).toHaveBeenCalledWith('r001');
    });
  });

  it('FV-004: 삭제 성공 후 해당 카드가 목록에서 제거된다', async () => {
    renderPage();
    const removeButtons = await screen.findAllByRole('button', { name: /즐겨찾기 해제/ });

    fireEvent.click(removeButtons[0]);
    await waitFor(() => {
      expect(screen.queryByText('김치찌개')).not.toBeInTheDocument();
    });
    expect(screen.getByText('된장찌개')).toBeInTheDocument();
  });

  it('FV-005: API 호출 실패 시 빈 상태 메시지가 표시된다', async () => {
    (api.getFavorites as jest.Mock).mockRejectedValueOnce(new Error('서버 오류'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/즐겨찾기한 레시피가 없어요/)).toBeInTheDocument();
    });
  });
});
