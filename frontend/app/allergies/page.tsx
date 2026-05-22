'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Leaf, Plus } from 'lucide-react';
import { Button } from '@/components/Button';
import { FridgeChip } from '@/components/FridgeChip';
import { useToast } from '@/components/Toast';
import { apiErrorMessage, getMe, updateAllergies } from '@/lib/api';

const PRESET_ALLERGIES = [
  '난류', '우유', '메밀', '땅콩', '대두', '밀', '고등어', '게',
  '새우', '돼지고기', '복숭아', '토마토', '아황산류', '호두',
  '닭고기', '쇠고기', '오징어', '조개류(굴, 전복, 홍합 포함)', '잣',
];

export default function AllergiesPage() {
  const toast = useToast();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const [selectedPresets, setSelectedPresets] = useState<Set<string>>(new Set());
  const [customAllergies, setCustomAllergies] = useState<string[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const me = await getMe();
        const presetSet = new Set(PRESET_ALLERGIES);
        const presets = new Set<string>();
        const customs: string[] = [];
        for (const a of me.allergies) {
          if (presetSet.has(a)) presets.add(a);
          else customs.push(a);
        }
        setSelectedPresets(presets);
        setCustomAllergies(customs);
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
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const handleNavigateBack = () => {
    if (isDirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 페이지를 떠나시겠습니까?')) return;
    router.push('/fridge');
  };

  const togglePreset = (name: string) => {
    setSelectedPresets((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
    setIsDirty(true);
  };

  const handleAdd = () => {
    const target = input.trim();
    if (!target) return;
    if (PRESET_ALLERGIES.includes(target)) {
      if (selectedPresets.has(target)) {
        toast.show(`'${target}'는 이미 선택된 기본 알레르기입니다.`, 'info');
      } else {
        setSelectedPresets((prev) => new Set(prev).add(target));
        toast.show(`'${target}' 기본 알레르기 버튼에서 선택되었습니다.`, 'success');
        setIsDirty(true);
      }
      setInput('');
      return;
    }
    if (customAllergies.includes(target)) {
      toast.show('이미 추가된 항목입니다.', 'info');
      return;
    }
    setCustomAllergies((prev) => [...prev, target]);
    setInput('');
    setIsDirty(true);
  };

  // NFR-USE-001: 알레르기 저장 → 이후 추천 시 해당 재료 포함 레시피 필터링
  const handleSave = async () => {
    setSaving(true);
    try {
      const merged = [...selectedPresets, ...customAllergies];
      await updateAllergies(merged);
      setIsDirty(false);
      toast.show('알레르기 정보가 저장되었습니다.', 'success');
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="max-w-2xl mx-auto px-6 py-12 space-y-10">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-3xl font-bold flex items-center gap-2">
          <Leaf className="h-7 w-7 text-gochu-500" aria-hidden="true" />
          알레르기 수정
        </h1>
        <button
          type="button"
          onClick={handleNavigateBack}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 dark:text-cream-200 hover:text-gochu-500"
        >
          <ArrowLeft className="h-4 w-4" /> 메인화면으로 돌아가기
        </button>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-clay-700 dark:text-cream-200">
          기본 알레르기
          <span className="ml-2 font-normal text-clay-500">눌러서 선택 · 다시 눌러서 해제</span>
        </h2>
        {loading ? (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 10 }).map((_, i) => (
              <span key={i} className="skeleton h-9 w-16 rounded-xl" />
            ))}
          </div>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {PRESET_ALLERGIES.map((name) => {
              const active = selectedPresets.has(name);
              return (
                <li key={name}>
                  <button
                    type="button"
                    onClick={() => togglePreset(name)}
                    className={`px-3 py-1.5 rounded-xl text-sm font-semibold border-2 transition-colors ${
                      active
                        ? 'bg-gochu-500 border-gochu-500 text-white'
                        : 'bg-cream-50 dark:bg-clay-800 border-clay-900 dark:border-cream-100/30 text-clay-700 dark:text-cream-200 hover:border-gochu-500'
                    }`}
                    aria-pressed={active}
                  >
                    {active && <span className="mr-1">✓</span>}
                    {name}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <hr className="border-clay-900/10 dark:border-cream-100/10" />

      <section className="space-y-4">
        <h2 className="text-sm font-semibold text-clay-700 dark:text-cream-200">직접 추가</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="예: 키위, 망고…"
            maxLength={20}
            className="flex-1 rounded-2xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 px-4 h-12 outline-none text-sm"
          />
          <Button size="sm" variant="primary" onClick={handleAdd} disabled={!input.trim()}>
            <Plus className="h-4 w-4" /> 추가
          </Button>
        </div>
        {customAllergies.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {customAllergies.map((a) => (
              <li key={a}>
                <FridgeChip name={a} onRemove={() => { setCustomAllergies((prev) => prev.filter((x) => x !== a)); setIsDirty(true); }} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <Button variant="primary" onClick={handleSave} loading={saving}>
        저장하기
      </Button>
    </main>
  );
}
