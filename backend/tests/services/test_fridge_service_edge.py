"""fridge_service 권한 격리 테스트 (FS-001 ~ FS-003).

보안 경계 케이스:
- FS-001: 동의어 정규화 정상 동작 확인 (쪽파 → 대파)
- FS-002: 존재하지 않는 재료 삭제 시 False 반환 (서버 안전)
- FS-003: 다른 사용자의 재료 삭제 시도 시 False 반환 (권한 격리)
"""

from __future__ import annotations

import pytest

from app.models.orm import User
from app.schemas.fridge import IngredientCreate
from app.services import fridge_service


async def _insert_user(db, email: str, nickname: str = "테스터") -> User:
    """테스트용 유저를 DB에 직접 삽입 후 반환."""
    user = User(
        email=email,
        password_hash="test_hash_not_real",
        nickname=nickname,
        allergies=[],
        preferences={},
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestFridgeServiceEdge:
    """FS-001 ~ FS-003: fridge_service 서비스 계층 경계 케이스."""

    @pytest.mark.asyncio
    async def test_fs001_add_synonym_normalized_to_canonical(self, db_session):
        """FS-001: '쪽파' 추가 시 normalized_name이 '대파'로 저장된다."""
        user = await _insert_user(db_session, "fs001@test.com")
        payload = IngredientCreate(raw_name="쪽파")

        item = await fridge_service.add_for_user(db_session, user.id, payload)

        assert item.raw_name == "쪽파"
        assert item.normalized_name == "대파"

    @pytest.mark.asyncio
    async def test_fs002_delete_nonexistent_ingredient_returns_false(self, db_session):
        """FS-002: 존재하지 않는 ID(99999)로 삭제 요청 시 False를 반환한다."""
        user = await _insert_user(db_session, "fs002@test.com")

        result = await fridge_service.delete_for_user(db_session, user.id, 99999)

        assert result is False

    @pytest.mark.asyncio
    async def test_fs003_delete_other_users_ingredient_returns_false(self, db_session):
        """FS-003: 다른 사용자의 재료를 삭제 시도하면 False를 반환한다 (권한 차단).

        # NFR-SEC-004 — 냉장고 재료는 소유자만 접근·삭제 가능해야 한다.
        # (회원 탈퇴 시 자기 데이터 파기 보장의 전제 조건: 다른 유저가 먼저 삭제 불가)
        """
        user_a = await _insert_user(db_session, "fs003a@test.com", "사용자A")
        user_b = await _insert_user(db_session, "fs003b@test.com", "사용자B")

        payload = IngredientCreate(raw_name="당근")
        item = await fridge_service.add_for_user(db_session, user_a.id, payload)

        # user_b가 user_a 소유의 재료를 삭제 시도
        result = await fridge_service.delete_for_user(db_session, user_b.id, item.id)

        assert result is False
        # user_a의 재료는 여전히 존재해야 함
        remaining = await fridge_service.list_for_user(db_session, user_a.id)
        assert any(r.id == item.id for r in remaining)
