'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Clock, Star, ChefHat, Flame, Globe2, ImageOff } from 'lucide-react';
import { BrandLockup } from '@/components/Brand';
import { useToast } from '@/components/Toast';
import { apiErrorMessage, getFavorites, removeFavorite, type FavoriteItem } from '@/lib/api';

export default function FavoritesPage() {
  const toast = useToast();
  const [items, setItems] = useState<FavoriteItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const data = await getFavorites();
        setItems(data.items);
      } catch (err) {
        toast.show(apiErrorMessage(err), 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleRemove = async (recipe_id: string) => {
    try {
      await removeFavorite(recipe_id);
      setItems((prev) => prev.filter((i) => i.recipe_id !== recipe_id));
      toast.show('즐겨찾기에서 제거했습니다.', 'success');
    } catch (err) {
      toast.show(apiErrorMessage(err), 'error');
    }
  };

  return (
    <main className="min-h-screen bg-cream-100 dark:bg-clay-900">
      <header className="px-6 lg:px-12 py-6 border-b-2 border-clay-900/10 dark:border-cream-100/10">
        <BrandLockup size="md" href="/fridge" />
      </header>

      <div className="max-w-5xl mx-auto px-6 lg:px-12 py-10">
        <h1 className="font-display text-4xl font-bold tracking-tight mb-2">
          <span className="ink-underline">즐겨찾기</span>
        </h1>
        <p className="text-clay-600 dark:text-clay-400 mb-8">
          {loading ? '' : `${items.length}개의 레시피`}
        </p>

        {loading && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="skeleton h-56 rounded-3xl" />
            ))}
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-24">
            <Star className="h-12 w-12 text-clay-300 mx-auto mb-4" />
            <p className="text-clay-500 font-semibold">즐겨찾기한 레시피가 없어요.</p>
            <Link
              href="/recommend"
              className="mt-6 inline-flex items-center gap-2 h-11 px-6 rounded-full bg-clay-900 dark:bg-cream-100 text-cream-50 dark:text-clay-900 font-semibold"
            >
              레시피 추천받기
            </Link>
          </div>
        )}

        {!loading && items.length > 0 && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {items.map((item, i) => (
              <motion.div
                key={item.recipe_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.05 }}
                className="relative rounded-3xl border-2 border-clay-900 dark:border-cream-100 bg-cream-50 dark:bg-clay-800 shadow-sticker overflow-hidden"
              >
                {/* 이미지 */}
                <Link href={`/recipe/${item.recipe_id}`}>
                  <div className="relative aspect-video bg-cream-200 dark:bg-clay-700">
                    {item.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.image_url}
                        alt={item.name}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="h-full w-full flex items-center justify-center text-clay-400">
                        <ImageOff className="h-8 w-8" />
                      </div>
                    )}
                  </div>
                </Link>

                {/* 정보 */}
                <div className="p-4">
                  <Link href={`/recipe/${item.recipe_id}`}>
                    <h2 className="font-display font-bold text-lg leading-tight hover:text-gochu-500 transition-colors line-clamp-2">
                      {item.name}
                    </h2>
                  </Link>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-clay-500">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> {item.cook_min}분
                    </span>
                    <span className="flex items-center gap-1">
                      <ChefHat className="h-3 w-3" /> Lv {item.difficulty_level}
                    </span>
                    <span className="flex items-center gap-1">
                      <Flame className="h-3 w-3" /> {item.spicy}/5
                    </span>
                    {item.country && (
                      <span className="flex items-center gap-1">
                        <Globe2 className="h-3 w-3" /> {item.country}
                      </span>
                    )}
                  </div>
                </div>

                {/* 즐겨찾기 해제 버튼 */}
                <button
                  onClick={() => handleRemove(item.recipe_id)}
                  className="absolute top-3 right-3 h-8 w-8 flex items-center justify-center rounded-full bg-cream-50/80 dark:bg-clay-800/80 backdrop-blur border-2 border-clay-900/20 hover:border-gochu-500 hover:text-gochu-500 transition-colors"
                  aria-label="즐겨찾기 해제"
                >
                  <Star className="h-4 w-4 fill-gochu-500 text-gochu-500" />
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
