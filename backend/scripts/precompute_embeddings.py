"""1667 레시피 description → multilingual-e5-small 문장 임베딩 사전계산 → .npz 캐시.

왜 사전계산하나:
  - 시동마다 1667개를 인코딩하면 수십 초~분 소요 + 매번 모델 추론. 오프라인 1회 계산 후
    캐시(.npz)만 로드하면 운영 시동이 빨라지고, 요청 시엔 쿼리 1건만 인코딩하면 된다.

e5 규약: 문서(레시피)는 "passage: " 접두사로 인코딩 (intfloat 공식 권장).

실행:
    cd backend && python scripts/precompute_embeddings.py
출력:
    backend/data/recipe_embeddings.npz  (recipe_ids[N], embeddings[N, dim] 정규화)

데이터 출처 우선순위:
  1. data/recipe_descriptions.json (recipe_id -> 자연어 설명) — 의미 매칭의 핵심 텍스트
  2. /tmp/recipes_1667.pkl (이름 보강용, 있으면) — "passage: {이름}. {설명}"
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

DESCRIPTIONS_PATH = _BACKEND_DIR / "data" / "recipe_descriptions.json"
NAMES_CACHE = Path("/tmp/recipes_1667.pkl")
OUT_PATH = _BACKEND_DIR / "data" / "recipe_embeddings.npz"
MODEL_NAME = "intfloat/multilingual-e5-small"


def _load_names() -> dict[str, str]:
    """recipe_id -> 이름 (있으면). 캐시 부재 시 빈 dict."""
    if not NAMES_CACHE.exists():
        return {}
    try:
        with NAMES_CACHE.open("rb") as f:
            rows = pickle.load(f)
        return {str(r["recipe_id"]): str(r.get("name", "")) for r in rows}
    except Exception as e:  # noqa: BLE001
        print(f"⚠ 이름 캐시 로드 실패({e}) — 설명만 사용")
        return {}


def main() -> int:
    if not DESCRIPTIONS_PATH.exists():
        print(f"❌ {DESCRIPTIONS_PATH} 없음")
        return 1
    descriptions: dict[str, str] = json.loads(DESCRIPTIONS_PATH.read_text(encoding="utf-8"))
    names = _load_names()
    print(f"설명 {len(descriptions)}건, 이름 {len(names)}건 로드")

    recipe_ids: list[str] = []
    texts: list[str] = []
    for rid, desc in descriptions.items():
        rid = str(rid)
        name = names.get(rid, "")
        body = f"{name}. {desc}".strip(". ").strip() if name else (desc or "")
        if not body:
            continue
        recipe_ids.append(rid)
        texts.append(f"passage: {body}")

    if not texts:
        print("❌ 인코딩할 텍스트 없음")
        return 1

    print(f"e5 모델 로드: {MODEL_NAME} ...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME)
    print(f"{len(texts)}개 인코딩 중 (정규화)...")
    import numpy as np

    emb = model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype("float32")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT_PATH,
        recipe_ids=np.array(recipe_ids, dtype=object),
        embeddings=emb,
    )
    size_mb = OUT_PATH.stat().st_size / 1e6
    print(f"✅ 저장 완료: {OUT_PATH}  ({len(recipe_ids)} docs, dim={emb.shape[1]}, {size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
