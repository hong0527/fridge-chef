'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { Button } from '@/components/Button';
import { apiErrorMessage, verifyEmail } from '@/lib/api';

type State = 'loading' | 'success' | 'error';

function VerifyEmailInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [state, setState] = useState<State>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const token = params.get('token');
    if (!token) {
      setErrorMsg('인증 토큰이 없습니다.');
      setState('error');
      return;
    }

    verifyEmail(token)
      .then(() => setState('success'))
      .catch((err) => {
        setErrorMsg(apiErrorMessage(err));
        setState('error');
      });
  }, [params]);

  return (
    <div className="w-full max-w-md rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker p-8 text-center space-y-6">
      {state === 'loading' && (
        <>
          <Loader2 className="h-12 w-12 mx-auto animate-spin text-clay-500" />
          <p className="font-semibold text-lg">이메일 인증 중...</p>
        </>
      )}

      {state === 'success' && (
        <>
          <CheckCircle2 className="h-12 w-12 mx-auto text-herb-600 dark:text-herb-400" />
          <div>
            <p className="font-bold text-xl">인증 완료!</p>
            <p className="mt-2 text-sm text-clay-600 dark:text-clay-400">
              이메일 인증이 완료되었어요. 로그인해주세요.
            </p>
          </div>
          <Button variant="primary" size="lg" className="w-full" onClick={() => router.push('/auth?mode=login')}>
            로그인하러 가기
          </Button>
        </>
      )}

      {state === 'error' && (
        <>
          <XCircle className="h-12 w-12 mx-auto text-gochu-500" />
          <div>
            <p className="font-bold text-xl">인증 실패</p>
            <p className="mt-2 text-sm text-clay-600 dark:text-clay-400">{errorMsg}</p>
          </div>
          <Button variant="secondary" size="lg" className="w-full" onClick={() => router.push('/auth?mode=login')}>
            로그인 페이지로 이동
          </Button>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900 flex flex-col">
      <header className="max-w-7xl w-full mx-auto px-6 lg:px-12 py-6">
        <BrandLockup size="md" />
      </header>
      <div className="flex-1 flex items-center justify-center px-6">
        <Suspense fallback={<Loader2 className="h-12 w-12 animate-spin text-clay-500" />}>
          <VerifyEmailInner />
        </Suspense>
      </div>
    </main>
  );
}
