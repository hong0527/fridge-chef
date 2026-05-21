"""유닛 테스트 — schemas/auth.py 신규 스키마 (AI 생성)"""
import pytest
from pydantic import ValidationError
from app.schemas.auth import UpdateProfileRequest, UpdateAllergiesRequest


class TestUpdateProfileRequest:
    def test_all_none_raises(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest()

    def test_nickname_only(self):
        req = UpdateProfileRequest(nickname="홍길동")
        assert req.nickname == "홍길동"
        assert req.new_password is None

    def test_new_password_only(self):
        req = UpdateProfileRequest(new_password="securepass")
        assert req.new_password == "securepass"
        assert req.nickname is None

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(new_password="1234567")  # 7자

    def test_empty_nickname_raises(self):
        with pytest.raises(ValidationError):
            UpdateProfileRequest(nickname="")

    def test_both_fields_valid(self):
        req = UpdateProfileRequest(nickname="홍", new_password="newpass1")
        assert req.nickname == "홍"
        assert req.new_password == "newpass1"


class TestUpdateAllergiesRequest:
    def test_valid_list(self):
        req = UpdateAllergiesRequest(allergies=["땅콩", "새우"])
        assert req.allergies == ["땅콩", "새우"]

    def test_empty_list_allowed(self):
        req = UpdateAllergiesRequest(allergies=[])
        assert req.allergies == []

    def test_default_is_empty(self):
        req = UpdateAllergiesRequest()
        assert req.allergies == []
