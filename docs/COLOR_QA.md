# COLOR 0.2.1 — 검증 기록

- PASS: pytest 72개, Ruff 검사·포맷.
- PASS: `color 0A`, `1F`, `F0`, `84`, 한 자리 `A`/`E`, 대소문자 처리.
- PASS: 동일 코드·잘못된 16진수·추가 인자·셸 구문 거부 및 기존 테마 보존.
- PASS: 실제 Qt 콘솔·입력·상태 글자 팔레트, 전체 이전 출력 재색상, 기본 테마 복원.
- PASS: `color /?` 도움말, ERRORLEVEL 0/1, 디스크 설정 미변경, subprocess 호출 없음.
- PASS: 선택한 배경과 Swarm Replay 배경 일치.
- PASS: Windows 단일 EXE·Portable EXE의 COLOR·복원·동일 색 거부 및 색상 적용 인트로.
- PASS: 실제 Windows 0A/1F/F0/기본 테마 캡처 (`assets/screenshots/colors`).

지원 예:

```text
color 0A
color 1F
color F0
color A
color /?
color
```

첫째 자리는 배경, 둘째는 글자입니다. 한 자리는 검정 배경과 해당 글자색을 선택합니다.
`color` 단독은 시작 테마를 복원합니다. 변경은 현재 JACK GUARD 창에만 적용됩니다.
클래식 RGB 16색을 사용하므로 사용자가 변경한 CMD/Windows Terminal 팔레트와는 다를 수 있습니다.
