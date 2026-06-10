/**
 * @jest-environment node
 */
import { NextRequest, NextResponse } from 'next/server';
import { middleware } from '@/middleware';

function makeReq(pathname: string, hasCookie = false): NextRequest {
  const headers = new Headers();
  if (hasCookie) headers.set('Cookie', 'fc_auth=1');
  return new NextRequest(`http://localhost${pathname}`, { headers });
}

describe('middleware — 인증 가드 (I-MW-01~07)', () => {
  it('I-MW-01: 미로그인 → /fridge → /auth 리다이렉트', () => {
    const res = middleware(makeReq('/fridge', false));
    expect(res).toBeInstanceOf(NextResponse);
    expect(res.headers.get('location')).toContain('/auth');
  });

  it('I-MW-02: 미로그인 → /profile → /auth 리다이렉트', () => {
    const res = middleware(makeReq('/profile', false));
    expect(res.headers.get('location')).toContain('/auth');
  });

  it('I-MW-03: 미로그인 → /allergies → /auth 리다이렉트', () => {
    const res = middleware(makeReq('/allergies', false));
    expect(res.headers.get('location')).toContain('/auth');
  });

  it('I-MW-04: 로그인 → /auth 접근 → /fridge 리다이렉트', () => {
    const res = middleware(makeReq('/auth', true));
    expect(res.headers.get('location')).toContain('/fridge');
  });

  it('I-MW-05: 로그인 → /fridge → 리다이렉트 없이 통과', () => {
    const res = middleware(makeReq('/fridge', true));
    // NextResponse.next()는 location 헤더가 없음
    expect(res.headers.get('location')).toBeNull();
  });

  it('I-MW-06: 미로그인 → matcher 외 경로 → 통과', () => {
    // /recommend는 matcher에 포함되지 않으므로 middleware 자체가 실행되지 않음.
    // middleware 내부에서는 isProtected=false → NextResponse.next()
    const res = middleware(makeReq('/recommend', false));
    expect(res.headers.get('location')).toBeNull();
  });

  it('I-MW-07: 미로그인 → /auth 접근 → 리다이렉트 없이 통과', () => {
    // fc_auth 쿠키 없이 /auth 접근 → 로그인 페이지 정상 표시 (리다이렉트 없음)
    // middleware.ts line 16: return NextResponse.next() (if auth 블록 안, 쿠키 없는 경우)
    const res = middleware(makeReq('/auth', false));
    expect(res.headers.get('location')).toBeNull();
  });
});
