# Pull Request

## 변경 요약
<!-- 1~3줄로 핵심만 -->

## 관련 이슈 / 문서
- SRS: FR-XXX, NFR-XXX-NNN
- SDD: §X.X
- Issue: #

## 변경 유형
- [ ] feat (새 기능)
- [ ] fix (버그 수정)
- [ ] refactor (리팩토링)
- [ ] docs
- [ ] chore / infra
- [ ] test

## 체크리스트
- [ ] 로컬에서 `pytest -q` 통과
- [ ] 로컬에서 `npx tsc --noEmit` 통과
- [ ] NFR 추적 주석 (`# NFR-XXX-NNN`) 추가
- [ ] 환경변수 변경 시 `.env.example` 업데이트
- [ ] 마이그레이션 변경 시 `db/migrations/` 또는 alembic 리비전 추가

## AI Usage (필수)
<!--
어떤 AI 도구를 어떻게 썼는지 투명하게 기록.
- 도구명 / 모델 / 버전
- 무엇을 생성·수정했는지
- 사람이 직접 검증한 범위
예) "Claude Code Opus 4.7 — model_a.py 초안 + pytest 케이스. 모든 테스트 결과는 본인이 직접 실행하여 확인."
-->

## 테스트
<!-- 어떤 명령으로 확인했는지, 화면이라면 스크린샷 -->

## 리스크 / 후속 작업
<!-- 알려진 한계, TODO -->
