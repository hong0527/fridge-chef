'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Lock, Mail, User } from 'lucide-react';
import { Button } from '@/components/Button';
import { useToast } from '@/components/Toast';
import { apiErrorMessage, getMe, updateProfile } from '@/lib/api';
import { useNavigationGuard } from '@/lib/navigationGuard';

export default function ProfilePage() {
  const toast = useToast();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [savingNickname, setSavingNickname] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const [email, setEmail] = useState('');
  const [nickname, setNickname] = useState('');
  const [originalNickname, setOriginalNickname] = useState('');
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');

  const isDirty = nickname !== originalNickname || currentPw !== '' || newPw !== '' || confirmPw !== '';
  const { setIsDirty: setGuardDirty } = useNavigationGuard();

  // 사이드바 네비게이션 가드에 isDirty 동기화
  useEffect(() => { setGuardDirty(isDirty); }, [isDirty, setGuardDirty]);

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        setEmail(me.email);
        setNickname(me.nickname);
        setOriginalNickname(me.nickname);
      } catch (err) {
        toast.show(apiErrorMessage(err), 'error');
      } finally {
        setLoading(false);
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) { e.preventDefault(); e.returnValue = ''; }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const handleNavigateBack = () => {
    if (isDirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 페이지를 떠나시겠습니까?')) return;
    setGuardDirty(false);
    router.push('/fridge');
  };

  const handleSaveNickname = async () => {
    if (!nickname.trim()) return;
    setSavingNickname(true);
    try {
      await updateProfile({ nickname: nickname.trim() });
      setOriginalNickname(nickname.trim());
      toast.show('닉네임이 수정되었습니다.', 'success');
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    } finally {
      setSavingNickname(false);
    }
  };

  // NFR-SEC-001: 비밀번호 최소 8자 클라이언트 검증 + bcrypt 해시는 백엔드에서 처리
  const handleChangePassword = async () => {
    if (!currentPw || !newPw || !confirmPw) {
      toast.show('모든 비밀번호 칸을 입력해주세요.', 'warning');
      return;
    }
    if (newPw.length < 8) {
      toast.show('새 비밀번호는 8자 이상이어야 합니다.', 'warning');
      return;
    }
    if (newPw !== confirmPw) {
      toast.show('새 비밀번호와 새 비밀번호 확인이 일치하지 않습니다.', 'warning');
      return;
    }
    setSavingPassword(true);
    try {
      await updateProfile({ current_password: currentPw, new_password: newPw });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
      toast.show('비밀번호가 변경되었습니다.', 'success');
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    } finally {
      setSavingPassword(false);
    }
  };

  if (loading) {
    return (
      <main className="max-w-xl mx-auto px-6 py-12">
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton h-12 rounded-xl" />
          ))}
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-xl mx-auto px-6 py-12 space-y-10">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl font-bold flex items-center gap-2">
          <User className="h-7 w-7 text-gochu-500" aria-hidden="true" />
          회원정보 수정
        </h1>
        <button
          type="button"
          onClick={handleNavigateBack}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          <ArrowLeft className="h-4 w-4" /> 메인화면으로 돌아가기
        </button>
      </div>

      <section className="space-y-2">
        <label className="block text-sm font-semibold text-clay-700 dark:text-cream-200">이메일</label>
        <div className="flex items-center gap-2 rounded-2xl border-2 border-clay-900/30 dark:border-cream-100/20 bg-cream-50 dark:bg-clay-800 px-4 h-12">
          <Mail className="h-4 w-4 text-clay-400" aria-hidden="true" />
          <span className="text-clay-500 text-sm">{email}</span>
        </div>
      </section>

      <section className="space-y-3">
        <label htmlFor="nickname" className="block text-sm font-semibold text-clay-700 dark:text-cream-200">닉네임</label>
        <input
          id="nickname"
          type="text"
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          maxLength={64}
          className="w-full rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 h-12 outline-none text-sm"
        />
        <Button size="sm" variant="primary" onClick={handleSaveNickname} loading={savingNickname}>
          닉네임 저장
        </Button>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-clay-700 dark:text-cream-200 flex items-center gap-2">
          <Lock className="h-4 w-4" aria-hidden="true" />
          비밀번호 변경
        </h2>
        <input
          type="password"
          placeholder="현재 비밀번호"
          value={currentPw}
          onChange={(e) => setCurrentPw(e.target.value)}
          className="w-full rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 h-12 outline-none text-sm"
        />
        <input
          type="password"
          placeholder="새 비밀번호 (8자 이상)"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
          className="w-full rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 h-12 outline-none text-sm"
        />
        <input
          type="password"
          placeholder="새 비밀번호 확인"
          value={confirmPw}
          onChange={(e) => setConfirmPw(e.target.value)}
          className="w-full rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 h-12 outline-none text-sm"
        />
        {confirmPw && (
          <p className={`text-xs font-semibold ${newPw === confirmPw ? 'text-herb-500' : 'text-gochu-500'}`}>
            {newPw === confirmPw ? '✓ 비밀번호가 일치합니다' : '✗ 비밀번호가 일치하지 않습니다'}
          </p>
        )}
        <Button size="sm" variant="primary" onClick={handleChangePassword} loading={savingPassword}>
          비밀번호 변경
        </Button>
      </section>
    </main>
  );
}
