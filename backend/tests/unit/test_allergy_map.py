"""유닛 테스트 — allergy_map.py (AI 생성)"""
import pytest
from app.core.allergy_map import expand_allergies, ALLERGY_EXPANSION


class TestExpandAllergies:
    def test_난류_expands_to_계란_달걀(self):
        result = expand_allergies(["난류"])
        assert "계란" in result
        assert "달걀" in result

    def test_조개류_expands_to_굴_전복_홍합(self):
        result = expand_allergies(["조개류(굴, 전복, 홍합 포함)"])
        assert "굴" in result
        assert "전복" in result
        assert "홍합" in result

    def test_쇠고기_includes_소고기(self):
        result = expand_allergies(["쇠고기"])
        assert "소고기" in result

    def test_소고기_includes_쇠고기(self):
        """I-06 수정 확인 — 두 키 모두 등재"""
        result = expand_allergies(["소고기"])
        assert "쇠고기" in result

    def test_custom_allergen_no_expansion(self):
        result = expand_allergies(["키위"])
        assert result == ["키위"]

    def test_empty_list(self):
        assert expand_allergies([]) == []

    def test_deduplication(self):
        """난류 + 계란 동시 입력 시 계란 중복 없음"""
        result = expand_allergies(["난류", "계란"])
        assert result.count("계란") == 1

    def test_multiple_presets(self):
        result = expand_allergies(["난류", "새우"])
        assert "계란" in result
        assert "왕새우" in result

    def test_all_19_presets_registered(self):
        """프리셋 19개 전체 ALLERGY_EXPANSION에 등재 확인"""
        presets = [
            "난류", "우유", "메밀", "땅콩", "대두", "밀", "고등어", "게",
            "새우", "돼지고기", "복숭아", "토마토", "아황산류", "호두",
            "닭고기", "쇠고기", "오징어", "조개류(굴, 전복, 홍합 포함)", "잣",
        ]
        for preset in presets:
            assert preset in ALLERGY_EXPANSION, f"{preset} 미등재"
