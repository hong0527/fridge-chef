'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Lock, User, ArrowRight, CheckCircle2 } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { Button } from '@/components/Button';
import { Modal } from '@/components/Modal';
import { useToast } from '@/components/Toast';
import { apiErrorMessage, login, setAllergies, signup } from '@/lib/api';
import { cn } from '@/lib/cn';

type Mode = 'login' | 'signup';

function AuthInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();

  const initialMode: Mode = params.get('mode') === 'signup' ? 'signup' : 'login';
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [nickname, setNickname] = useState('');
  const [loading, setLoading] = useState(false);
  const [verifyOpen, setVerifyOpen] = useState(false);

  useEffect(() => {
    const m = params.get('mode');
    if (m === 'signup' || m === 'login') setMode(m);
  }, [params]);

  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const validPassword = password.length >= 8;
  const validNickname = nickname.length >= 1 && nickname.length <= 30;
  const matches = mode === 'signup' ? password === confirm && confirm.length > 0 : true;
  const canSubmit =
    validEmail &&
    validPassword &&
    matches &&
    (mode === 'login' || validNickname) &&
    !loading;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    try {
      if (mode === 'signup') {
        // 백엔드 signup 응답은 UserPublic (토큰 없음). 회원가입 후 자동 로그인.
        const user = await signup(email, password, nickname);
        setAllergies(user.allergies);
        await login(email, password);
        setVerifyOpen(true);
      } else {
        await login(email, password);
        toast.show('로그인 완료', 'success');
        router.push('/fridge');
      }
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900 flex flex-col">
      <header className="max-w-7xl w-full mx-auto px-6 lg:px-12 py-6">
        <BrandLockup size="md" />
      </header>

      <div className="flex-1 flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">
          <div className="relative rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker p-7 sm:p-9">
            {/* Mode toggle */}
            <div
              role="tablist"
              aria-label="로그인 또는 회원가입 선택"
              className="relative grid grid-cols-2 p-1 rounded-full bg-cream-200 dark:bg-clay-700 mb-7"
            >
              <motion.span
                layout
                transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                className={cn(
                  'absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-full bg-clay-900 dark:bg-cream-100',
                  mode === 'login' ? 'left-1' : 'left-[calc(50%+3px)]',
                )}
                aria-hidden="true"
              />
              {(['login', 'signup'] as Mode[]).map((m) => (
                <button
                  key={m}
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className={cn(
                    'relative z-10 h-10 rounded-full font-semibold text-sm transition-colors',
                    mode === m
                      ? 'text-cream-50 dark:text-clay-900'
                      : 'text-clay-700 dark:text-cream-200',
                  )}
                  type="button"
                >
                  {m === 'login' ? '로그인' : '회원가입'}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={mode}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.24 }}
              >
                <h1 className="font-display text-3xl font-bold leading-tight">
                  {mode === 'login' ? (
                    <>
                      다시 오신 걸<br />환영해요.
                    </>
                  ) : (
                    <>
                      오늘부터<br />함께 요리해요.
                    </>
                  )}
                </h1>
                <p className="mt-2 text-sm text-clay-600 dark:text-clay-400">
                  {mode === 'login'
                    ? '냉장고에 무엇이 남았는지 들여다볼 시간이에요.'
                    : '이메일 인증 후, 첫 추천을 받아보세요.'}
                </p>
              </motion.div>
            </AnimatePresence>

            <form onSubmit={handleSubmit} className="mt-7 space-y-4" noValidate>
              <Field
                id="email"
                type="email"
                label="이메일"
                icon={<Mail className="h-4 w-4" />}
                value={email}
                onChange={setEmail}
                autoComplete="email"
                placeholder="you@example.com"
                error={email.length > 0 && !validEmail ? '올바른 이메일을 입력하세요' : undefined}
              />
              <Field
                id="password"
                type="password"
                label="비밀번호"
                icon={<Lock className="h-4 w-4" />}
                value={password}
                onChange={setPassword}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="8자 이상"
                error={password.length > 0 && !validPassword ? '8자 이상 입력하세요' : undefined}
              />
              {mode === 'signup' && (
                <>
                  <Field
                    id="confirm"
                    type="password"
                    label="비밀번호 확인"
                    icon={<Lock className="h-4 w-4" />}
                    value={confirm}
                    onChange={setConfirm}
                    autoComplete="new-password"
                    placeholder="다시 한 번 입력"
                    error={confirm.length > 0 && !matches ? '비밀번호가 일치하지 않습니다' : undefined}
                  />
                  <Field
                    id="nickname"
                    type="text"
                    label="닉네임"
                    icon={<User className="h-4 w-4" />}
                    value={nickname}
                    onChange={setNickname}
                    autoComplete="nickname"
                    placeholder="1~30자"
                    error={
                      nickname.length > 0 && !validNickname
                        ? '닉네임은 1~30자여야 합니다'
                        : undefined
                    }
                  />
                </>
              )}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                loading={loading}
                disabled={!canSubmit}
              >
                {mode === 'login' ? '로그인' : '회원가입'}
                <ArrowRight className="h-5 w-5" />
              </Button>
            </form>

            <p className="mt-6 text-xs text-clay-500 dark:text-clay-400 text-center">
              비밀번호는 서버에서 bcrypt로 안전하게 해시 저장됩니다.
            </p>
          </div>
        </div>
      </div>

      <Modal
        open={verifyOpen}
        onClose={() => {
          setVerifyOpen(false);
          router.push('/fridge');
        }}
        title="가입이 완료되었어요"
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-2xl bg-herb-500/10 border-2 border-herb-500/40 p-4">
            <CheckCircle2 className="h-6 w-6 shrink-0 text-herb-600 dark:text-herb-400" aria-hidden="true" />
            <div className="text-sm leading-relaxed">
              <p className="font-bold text-herb-700 dark:text-herb-400">
                {email}
              </p>
              <p className="text-clay-700 dark:text-cream-200 mt-1">
                회원가입이 완료되었습니다. 바로 냉장고 페이지로 이동합니다.
              </p>
            </div>
          </div>
          <p className="text-xs text-clay-500 dark:text-clay-400">
            ※ 이메일 인증 단계는 v2 릴리스에서 추가될 예정입니다 (SRS v1.11 격리).
          </p>
          <Button
            variant="primary"
            size="md"
            className="w-full"
            onClick={() => {
              setVerifyOpen(false);
              router.push('/fridge');
            }}
          >
            확인
          </Button>
        </div>
      </Modal>
    </main>
  );
}

interface FieldProps {
  id: string;
  type: string;
  label: string;
  icon: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  placeholder?: string;
  error?: string;
}

function Field({ id, type, label, icon, value, onChange, autoComplete, placeholder, error }: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-bold tracking-wider uppercase text-clay-600 dark:text-clay-400 mb-1.5">
        {label}
      </label>
      <div
        className={cn(
          'flex items-center gap-2 rounded-2xl border-2 bg-cream-50 dark:bg-clay-900 px-4 h-12 transition-colors',
          error
            ? 'border-gochu-500'
            : 'border-clay-400 dark:border-cream-100/30 focus-within:border-clay-900 dark:focus-within:border-cream-100',
        )}
      >
        <span aria-hidden="true" className="text-clay-500">
          {icon}
        </span>
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          className="flex-1 bg-transparent outline-none text-base placeholder:text-clay-400"
        />
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-gochu-600 dark:text-gochu-400">
          {error}
        </p>
      )}
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-cream-100 dark:bg-clay-900" />}>
      <AuthInner />
    </Suspense>
  );
}
