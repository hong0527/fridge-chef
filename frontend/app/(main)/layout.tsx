'use client';

import { usePathname, useRouter } from 'next/navigation';
import { Leaf, LogOut, Refrigerator, Star, User } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { logout } from '@/lib/api';
import { useToast } from '@/components/Toast';
import { NavigationGuardProvider, useNavigationGuard } from '@/lib/navigationGuard';

// NFR-USE-002: PC(1920px)·태블릿(768px) 반응형 사이드바
const NAV = [
  { href: '/fridge',     label: '내 냉장고',    icon: Refrigerator },
  { href: '/favorites',  label: '즐겨찾기',     icon: Star },
  { href: '/profile',    label: '프로필 설정',  icon: User },
  { href: '/allergies',  label: '알레르기 설정', icon: Leaf },
];

function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const toast = useToast();
  const { isDirty, setIsDirty } = useNavigationGuard();

  const handleNav = (href: string) => {
    if (isDirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 페이지를 떠나시겠습니까?')) return;
    setIsDirty(false);
    router.push(href);
  };

  const handleLogout = async () => {
    if (isDirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 로그아웃하시겠습니까?')) return;
    setIsDirty(false);
    await logout();
    toast.show('로그아웃 되었습니다.', 'success');
    router.push('/auth');
  };

  const linkClass = (href: string) =>
    `flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold transition-colors w-full text-left ${
      pathname === href
        ? 'bg-gochu-500 text-white'
        : 'text-clay-700 dark:text-cream-200 hover:bg-cream-200 dark:hover:bg-clay-800'
    }`;

  return (
    <aside className="hidden md:flex md:w-48 xl:w-64 shrink-0 flex-col py-8 px-4 border-r-2 border-clay-900/10 dark:border-cream-100/10 bg-cream-50 dark:bg-clay-800">
      <div className="mb-4 xl:mb-10 px-2">
        <BrandLockup size="md" href="/fridge" />
      </div>
      <nav className="flex flex-col gap-2 flex-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <button key={href} type="button" onClick={() => handleNav(href)} className={linkClass(href)}>
            <span className="flex items-center gap-3">
              <Icon className="h-6 w-6 shrink-0" aria-hidden="true" />
              {label}
            </span>
          </button>
        ))}
      </nav>
      <button
        type="button"
        onClick={handleLogout}
        className="flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold text-clay-600 dark:text-clay-400 hover:text-gochu-500 hover:bg-gochu-500/5 transition-colors"
      >
        <span className="flex items-center gap-3">
          <LogOut className="h-6 w-6 shrink-0" aria-hidden="true" />
          로그아웃
        </span>
      </button>
    </aside>
  );
}

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <NavigationGuardProvider>
      <div className="min-h-screen flex bg-cream-100 dark:bg-clay-900">
        <Sidebar />
        <div className="flex-1 min-w-0">
          {children}
        </div>
      </div>
    </NavigationGuardProvider>
  );
}
