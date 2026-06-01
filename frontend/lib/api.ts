import axios, { AxiosError, AxiosInstance } from 'axios';

/**
 * fridge-chef API client.
 * Base URL: NEXT_PUBLIC_API_URL (FastAPI 백엔드) + `/api` prefix
 * 인증: JWT Bearer 토큰 (localStorage.fc_token)
 */

const baseURL = `${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/api`;

const TOKEN_KEY = 'fc_token';
const ALLERGIES_KEY = 'fc_user_allergies';

export const getToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
};

// NFR-SEC-001: middleware 인증 가드용 쿠키 동기화 (localStorage만으로는 Edge Runtime 접근 불가)
export const setToken = (token: string | null) => {
  if (typeof window === 'undefined') return;
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
    document.cookie = 'fc_auth=1; path=/; SameSite=Lax';
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
    document.cookie = 'fc_auth=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
  }
};

/** SSR-safe 사용자 알레르기 캐시 접근 (recipe 상세에서 위반 경고용) */
export const getAllergies = (): string[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(ALLERGIES_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
};

export const setAllergies = (allergies: string[]) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(ALLERGIES_KEY, JSON.stringify(allergies));
};

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

// JWT 인터셉터
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      setToken(null);
      if (typeof window !== 'undefined' && window.location.pathname !== '/auth') {
        window.location.href = '/auth';
      }
    }
    return Promise.reject(err);
  },
);

// ============================================================
// Types — 백엔드 스키마 정합 (backend/app/schemas/*)
// ============================================================

/** TokenResponse — backend/app/schemas/auth.py (login 응답) */
export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

/** UserPublic — backend/app/schemas/auth.py (signup 응답) */
export interface UserPublic {
  id: number;
  email: string;
  nickname: string;
  allergies: string[];
  is_email_verified: boolean;
}

/** IngredientResponse — backend/app/schemas/fridge.py */
export interface Ingredient {
  id: number;
  raw_name: string;
  normalized_name: string;
  quantity: string | null;
  expires_at: string | null;
  created_at: string;
}

/** IngredientListResponse — backend/app/schemas/fridge.py */
export interface IngredientListResponse {
  items: Ingredient[];
  total: number;
}

/** Preferences — backend/app/schemas/recommend.py (RecommendPreferences) */
export interface Preferences {
  spicy: number;              // 1-5
  difficulty: string;         // 초보|중급|고급
  diet: boolean;
  use_saved_allergies: boolean;
  food_type: string;          // 메인요리|반찬|국물|디저트|음료
  country: string;            // 한식|중식|일식|양식|기타
  max_cook_min: number;       // 분
  user_context: string;
}

/** RecipeBrief — backend/app/schemas/recommend.py */
export interface RecipeBrief {
  recipe_id: string;
  name: string;
  cook_min: number;
  spicy: number;
  difficulty_level: number;
  country: string;
  theme: string;
}

/** ModelACandidate — 냉털 (코사인 유사도 score) */
export interface ModelACandidate extends RecipeBrief {
  score: number;
}

/** ModelBCandidate — 부족재료 + Gemini reason */
export interface ModelBCandidate extends RecipeBrief {
  final_score: number;
  have: string[];
  missing: string[];
  reason: string;
}

/** RecommendResponse — backend/app/schemas/recommend.py */
export interface RecommendResponse {
  model_a: ModelACandidate[];
  model_b: ModelBCandidate[];
}

/** GET /api/recipes/{id} — backend/app/api/recipes.py */
export interface Recipe {
  recipe_id: string;
  name: string;
  whole_ingredients: string[];
  steps: Array<{ order: number; text: string; image_url?: string }>;
  cook_min: number;
  spicy: number;
  difficulty_level: number;
  is_low_calorie: boolean;
  country: string;
  theme: string;
  allergens: string[];
  image_url?: string;
}

// ============================================================
// API functions
// ============================================================
export async function signup(
  email: string,
  password: string,
  nickname: string,
  allergies: string[] = [],
): Promise<UserPublic> {
  const { data } = await api.post<UserPublic>('/auth/signup', {
    email,
    password,
    nickname,
    allergies,
  });
  // signup 응답에는 토큰이 포함되지 않음 (백엔드 UserPublic). 호출자가 별도 login() 필요.
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(ALLERGIES_KEY, JSON.stringify(data.allergies));
  }
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>('/auth/login', { email, password });
  setToken(data.access_token);
  return data;
}

export async function logout(): Promise<void> {
  setToken(null);
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(ALLERGIES_KEY);
  }
}

export async function getFridge(): Promise<IngredientListResponse> {
  const { data } = await api.get<IngredientListResponse>('/fridge');
  return data;
}

export async function addIngredient(raw_name: string): Promise<Ingredient> {
  const { data } = await api.post<Ingredient>('/fridge', { raw_name });
  return data;
}

export async function removeIngredient(id: number): Promise<void> {
  await api.delete(`/fridge/${id}`);
}

export async function searchIngredients(query: string): Promise<string[]> {
  // SYNONYM_MAP 자동완성 (서버 측)
  const { data } = await api.get<{ suggestions: string[] }>('/ingredients/search', {
    params: { q: query },
  });
  return data.suggestions;
}

export async function recommend(
  fridge_ingredients: string[],
  prefs: Preferences,
): Promise<RecommendResponse> {
  const { data } = await api.post<RecommendResponse>('/recommend', {
    fridge_ingredients,
    preferences: prefs,
  });
  return data;
}

export async function getRecipe(id: string): Promise<Recipe> {
  const { data } = await api.get<Recipe>(`/recipes/${id}`);
  return data;
}

export interface UpdateProfileRequest {
  nickname?: string;
  current_password?: string;
  new_password?: string;
}

export async function getMe(): Promise<UserPublic> {
  const { data } = await api.get<UserPublic>('/auth/me');
  return data;
}

export async function updateProfile(payload: UpdateProfileRequest): Promise<UserPublic> {  // NFR-SEC-001
  const { data } = await api.patch<UserPublic>('/auth/me', payload);
  return data;
}

export async function verifyEmail(token: string): Promise<UserPublic> {
  const { data } = await api.post<UserPublic>('/auth/verify-email', { token });
  return data;
}

export async function updateAllergies(allergies: string[]): Promise<UserPublic> {  // FR-007
  const { data } = await api.patch<UserPublic>('/auth/me/allergies', { allergies });
  setAllergies(data.allergies);
  return data;
}

// ============================================================
// Error helper
// ============================================================
export function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? '').join(', ');
    return err.message;
  }
  return err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.';
}
