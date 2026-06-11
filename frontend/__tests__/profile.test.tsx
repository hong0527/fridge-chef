import '@testing-library/jest-dom';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { NavigationGuardProvider } from '@/lib/navigationGuard';
import { ToastProvider } from '@/components/Toast';
import ProfilePage from '@/app/(main)/profile/page';
import { getMe, updateProfile } from '@/lib/api';

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
  AnimatePresence: ({ children }: React.PropsWithChildren) =>
    React.createElement(React.Fragment, null, children),
}));

// api mock
jest.mock('@/lib/api', () => ({
  getMe: jest.fn(),
  updateProfile: jest.fn(),
  apiErrorMessage: jest.fn((err: unknown) => (err instanceof Error ? err.message : '오류')),
}));

const mockUser = {
  id: 1,
  email: 'test@test.com',
  nickname: '홍길동',
  allergies: [],
  is_email_verified: true,
};

function renderPage() {
  return render(
    <ToastProvider>
      <NavigationGuardProvider>
        <ProfilePage />
      </NavigationGuardProvider>
    </ToastProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(getMe).mockResolvedValue(mockUser);
});

describe('ProfilePage (I-FE-01~03)', () => {
  it('I-FE-01: 마운트 시 이메일을 표시한다', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('test@test.com')).toBeInTheDocument();
    });
  });

  it('I-FE-01: 마운트 시 닉네임 input에 값이 채워진다', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText('닉네임')).toHaveValue('홍길동');
    });
  });

  it('I-FE-02: 닉네임 저장 버튼 클릭 시 updateProfile을 호출한다', async () => {
    jest.mocked(updateProfile).mockResolvedValue({ ...mockUser, nickname: '새닉네임' });
    renderPage();
    await waitFor(() => screen.getByLabelText('닉네임'));

    fireEvent.change(screen.getByLabelText('닉네임'), { target: { value: '새닉네임' } });
    fireEvent.click(screen.getByRole('button', { name: '닉네임 저장' }));

    await waitFor(() => {
      expect(updateProfile).toHaveBeenCalledWith({ nickname: '새닉네임' });
    });
  });

  it('I-FE-03: 비밀번호 불일치 시 updateProfile을 호출하지 않는다', async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText('닉네임'));

    fireEvent.change(screen.getByPlaceholderText('새 비밀번호 (8자 이상)'), {
      target: { value: 'newpass1' },
    });
    fireEvent.change(screen.getByPlaceholderText('새 비밀번호 확인'), {
      target: { value: 'different' },
    });
    fireEvent.click(screen.getByRole('button', { name: '비밀번호 변경' }));

    expect(updateProfile).not.toHaveBeenCalled();
  });

  it('I-FE-03: 서버 400 오류 시 toast 에러 메시지가 DOM에 표시된다', async () => {
    jest.mocked(updateProfile).mockRejectedValueOnce(new Error('현재 비밀번호가 틀렸습니다'));
    renderPage();
    await waitFor(() => screen.getByLabelText('닉네임'));

    fireEvent.change(screen.getByPlaceholderText('현재 비밀번호'), {
      target: { value: 'oldpass1' },
    });
    fireEvent.change(screen.getByPlaceholderText('새 비밀번호 (8자 이상)'), {
      target: { value: 'newpass12' },
    });
    fireEvent.change(screen.getByPlaceholderText('새 비밀번호 확인'), {
      target: { value: 'newpass12' },
    });
    fireEvent.click(screen.getByRole('button', { name: '비밀번호 변경' }));

    await waitFor(() => {
      expect(screen.getByText('현재 비밀번호가 틀렸습니다')).toBeInTheDocument();
    });
  });

  it('I-FE-06: 닉네임 변경 시 NavigationGuard isDirty가 true로 반영된다', async () => {
    renderPage();
    await waitFor(() => screen.getByLabelText('닉네임'));

    fireEvent.change(screen.getByLabelText('닉네임'), { target: { value: '변경됨' } });

    // isDirty=true이면 beforeunload 이벤트 리스너가 등록되고 메인화면 버튼 클릭 시 confirm이 뜸
    // window.confirm을 mock하여 isDirty 상태를 간접 확인
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    fireEvent.click(screen.getByRole('button', { name: /메인화면으로 돌아가기/ }));
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });
});
