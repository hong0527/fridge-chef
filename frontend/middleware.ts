import { NextRequest, NextResponse } from 'next/server';

const PROTECTED = ['/fridge', '/profile', '/allergies'];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const auth = req.cookies.get('fc_auth');

  // 로그인 상태에서 /auth 접근 → /fridge로 리다이렉트
  if (pathname === '/auth' || pathname.startsWith('/auth/')) {
    if (auth) {
      const fridgeUrl = req.nextUrl.clone();
      fridgeUrl.pathname = '/fridge';
      return NextResponse.redirect(fridgeUrl);
    }
    return NextResponse.next();
  }

  // NFR-SEC-001: 미로그인 상태에서 보호 경로 접근 → /auth로 리다이렉트
  const isProtected = PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (!isProtected) return NextResponse.next();

  if (!auth) {
    const loginUrl = req.nextUrl.clone();
    loginUrl.pathname = '/auth';
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/fridge/:path*', '/profile/:path*', '/allergies/:path*', '/auth/:path*', '/auth'],
};
