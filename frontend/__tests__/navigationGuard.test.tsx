import '@testing-library/jest-dom';
import React from 'react';
import { render, act } from '@testing-library/react';
import { NavigationGuardProvider, useNavigationGuard } from '@/lib/navigationGuard';

function Consumer({
  onMount,
}: {
  onMount: (ctx: ReturnType<typeof useNavigationGuard>) => void;
}) {
  const ctx = useNavigationGuard();
  onMount(ctx);
  return null;
}

describe('NavigationGuard Context (U-NG-01~03)', () => {
  it('U-NG-01: Provider 마운트 시 isDirty 기본값은 false', () => {
    let ctx!: ReturnType<typeof useNavigationGuard>;
    render(
      <NavigationGuardProvider>
        <Consumer onMount={(c) => { ctx = c; }} />
      </NavigationGuardProvider>,
    );
    expect(ctx.isDirty).toBe(false);
  });

  it('U-NG-02: setIsDirty(true) 후 isDirty === true', () => {
    let ctx!: ReturnType<typeof useNavigationGuard>;
    render(
      <NavigationGuardProvider>
        <Consumer onMount={(c) => { ctx = c; }} />
      </NavigationGuardProvider>,
    );
    act(() => { ctx.setIsDirty(true); });
    expect(ctx.isDirty).toBe(true);
  });

  it('U-NG-03: setIsDirty(false) 후 isDirty === false로 복귀', () => {
    let ctx!: ReturnType<typeof useNavigationGuard>;
    render(
      <NavigationGuardProvider>
        <Consumer onMount={(c) => { ctx = c; }} />
      </NavigationGuardProvider>,
    );
    act(() => { ctx.setIsDirty(true); });
    act(() => { ctx.setIsDirty(false); });
    expect(ctx.isDirty).toBe(false);
  });
});
