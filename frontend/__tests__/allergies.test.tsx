import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NavigationGuardProvider } from '@/lib/navigationGuard';
import { ToastProvider } from '@/components/Toast';
import AllergiesPage from '@/app/(main)/allergies/page';
import { getMe, updateAllergies } from '@/lib/api';

// next/navigation mock
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), back: jest.fn() }),
}));

// framer-motion mock (ToastProvider 내부 AnimatePresence 처리)
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<React.HTMLAttributes<HTMLDivElement>>) =>
      React.createElement('div', props, children),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => React.createElement(React.Fragment, null, children),
}));

// api mock
jest.mock('@/lib/api', () => ({
  getMe: jest.fn(),
  updateAllergies: jest.fn(),
  apiErrorMessage: jest.fn((err: unknown) => (err instanceof Error ? err.message : '오류')),
}));

const mockUser = {
  id: 1,
  email: 't@t.com',
  nickname: '홍',
  allergies: ['땅콩', '키위'],
  is_email_verified: true,
};

function renderPage() {
  return render(
    <ToastProvider>
      <NavigationGuardProvider>
        <AllergiesPage />
      </NavigationGuardProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(getMe).mockResolvedValue(mockUser);
  jest.mocked(updateAllergies).mockResolvedValue(mockUser);
});

describe('AllergiesPage (I-FE-04~05)', () => {
  it('I-FE-04: 프리셋 알레르기 "땅콩"이 선택(aria-pressed=true)된다', async () => {
    renderPage();
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /땅콩/ });
      expect(btn).toHaveAttribute('aria-pressed', 'true');
    });
  });

  it('I-FE-04: 커스텀 알레르기 "키위"가 칩으로 표시된다', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('키위')).toBeInTheDocument();
    });
  });

  it('프리셋 버튼 클릭 시 aria-pressed가 토글된다', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: /새우/ });
    expect(btn).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(btn);
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('커스텀 알레르기 추가 후 칩 표시', async () => {
    renderPage();
    await waitFor(() => screen.getByPlaceholderText(/키위.*망고|망고.*키위|예:/));

    const input = screen.getByPlaceholderText(/예:/);
    fireEvent.change(input, { target: { value: '망고' } });
    fireEvent.click(screen.getByRole('button', { name: /추가/ }));

    expect(screen.getByText('망고')).toBeInTheDocument();
  });

  it('I-FE-05: 저장하기 클릭 시 updateAllergies를 프리셋+커스텀 합쳐서 호출한다', async () => {
    renderPage();
    await waitFor(() => screen.getByRole('button', { name: '저장하기' }));

    fireEvent.click(screen.getByRole('button', { name: '저장하기' }));

    await waitFor(() => {
      expect(updateAllergies).toHaveBeenCalledWith(
        expect.arrayContaining(['땅콩', '키위']),
      );
    });
  });

  it('I-FE-07: isDirty=false → 뒤로가기 클릭 시 confirm 없이 /fridge로 이동한다', async () => {
    renderPage();
    // 프리셋 버튼 로드 대기 (getMe 완료 후)
    await waitFor(() => screen.getByRole('button', { name: /새우/ }));

    const confirmSpy = jest.spyOn(window, 'confirm');
    fireEvent.click(screen.getByRole('button', { name: /메인화면으로 돌아가기/ }));

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith('/fridge');
    confirmSpy.mockRestore();
  });

  it('I-FE-07: isDirty=true → 뒤로가기 클릭 시 confirm 다이얼로그가 표시된다', async () => {
    renderPage();
    // 새우 버튼 클릭 → isDirty=true
    const presetBtn = await screen.findByRole('button', { name: /새우/ });
    fireEvent.click(presetBtn);

    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    fireEvent.click(screen.getByRole('button', { name: /메인화면으로 돌아가기/ }));

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
