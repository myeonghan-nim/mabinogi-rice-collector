# 마비노기 쌀 콜렉터 v2 — Go 전환 설계

2026-08-18. Python Discord 봇(main.py)을 Windows 11 이상에서 단독 실행되는 Go GUI 앱으로 전면 재작성한다.

## 확정된 결정

| # | 결정 | 내용 |
|---|---|---|
| 1 | Discord 완전 제거 | 알림은 Windows 토스트 + 시스템 트레이 + 인앱 로그로 대체. 봇 명령어(`!추가/!제거/!목록`)는 GUI로 대체 |
| 2 | 코드 서명 없음 | 2026-08 기준 무료 옵션은 SignPath Foundation뿐이나 외부 심사·릴리스별 수동 승인이 필요해 부적합. 서명 없이 배포하고 릴리스에 SHA-256 체크섬 첨부, README에 SmartScreen "추가 정보 → 실행" 안내 |
| 3 | 알림 중복 제거 | 아이템별 상태 추적: 조건 성립 + 직전 알림 가격과 다를 때만 알림. 조건 해제 시 상태 초기화 |
| 4 | 설정 기능 | 폴링 주기(기본 60초) 등 GUI 설정 화면 제공 |
| 5 | 테스트 | internal/core 전체 단위 테스트, CI에서 Windows 러너로 실행 |
| 6 | 버전 v2 | 현재 main을 v1.0.0으로 태깅 후 `feat!:` 커밋으로 v2.0.0부터 시작 |

## 기술 스택 (2026-08-18 웹 검증 완료)

- **Go 1.26** / 모듈 `github.com/myeonghan-nim/mabinogi-rice-collector`
- **Fyne v2.8.0** — GUI, 토스트(`SendNotification`), 트레이(`SetSystemTrayMenu`), 설정 저장(`Preferences`)
- **zalando/go-keyring v0.2.8** — 넥슨 API 키를 Windows 자격 증명 관리자에 저장 (Windows에서 cgo 불필요)
- **CI**: windows-2025 러너(gcc 사전 설치), actions/checkout@v7, actions/setup-go@v7, mathieudutour/github-tag-action@v6.2, softprops/action-gh-release@v3

## 구조

```
main.go                  # 부트스트랩, version 변수(-X 주입), 앱 ID, 로그 파일 설정
ui.go                    # Fyne UI 전체 (메인 창, 설정 다이얼로그, 트레이)
rsrc_windows_amd64.syso  # go-winres 생성 아이콘 리소스 (커밋, Windows 빌드에만 링크됨)
winres/                  # go-winres 설정 + 아이콘 원본
internal/core/
  nexon.go               # API 클라이언트: FetchLowestTwo(ctx, item) (lowest, next int64, err)
  monitor.go             # 폴링 루프 + 중복 제거 상태, OnLog/OnAlert 콜백
  format.go              # 천 단위 콤마, 알림 문구 생성, 아이템 이름 검증
  *_test.go
.github/workflows/ci.yml       # PR: go test + 빌드 (릴리스 리허설 겸용)
.github/workflows/release.yml  # main 푸시: 테스트 → 태그 → 빌드 → 릴리스
.github/dependabot.yml         # gomod + github-actions, prefix "chore" (릴리스 미발생)
```

`internal/core`는 Fyne을 import하지 않는다 — WSL2에서 GL 헤더 없이 `go test ./internal/...`가 돌고, 로직 테스트가 GUI와 분리된다.

## 핵심 동작 (Python 대비 보존/변경)

### 보존

- 엔드포인트 `GET https://open.api.nexon.com/mabinogi/v1/auction/keyword-search`, 헤더 `x-nxopen-api-key`, 쿼리 `keyword=<아이템명>` (첫 페이지만 사용 — 기존과 동일한 근사)
- `auction_item[]`을 `auction_price_per_unit` 오름차순 정렬 → `item_display_name`에 검색어가 부분일치하는 것 중 최저 2개 → (최저가, 차순위가)
- 특가 조건: 최저가 ≤ 차순위가 × 10% — int64 정확 연산 `lowest*10 <= next`
- HTTP 타임아웃 10초, 공유 클라이언트, 오류는 로그 남기고 다음 아이템/주기 진행 (429 포함 — Python과 동일하게 오류 로그 처리)
- 아이템 순차 조회, 매 주기 전체 목록 순회

### 변경

- **알림 채널**: Discord → ① Windows 토스트 ② 인앱 알림 로그 ③ 트레이 (창을 닫아도 트레이에서 감시 지속)
- **알림 문구**: Discord 마크다운 제거 — `🚨 <아이템> 특가! 일반 50,000 / 최저 4,000 / 할인율 92.0%` (콤마 포맷, 할인율 소수 1자리는 기존 유지)
- **중복 제거**: `lastAlerted[item]` 맵. 조건 성립 && `lowest != lastAlerted[item]` → 알림 후 갱신. 조건 미성립 → 항목 삭제(같은 가격 매물이 재등장하면 다시 알림)
- **폴링 주기**: 코드 상수 1초 → 설정값(기본 60초, 최소 1초). 주기는 "작업 후 대기"(sleep-after-work) 방식 — 사이클이 주기보다 길어도 API 연타 없음, 주기 변경은 다음 사이클부터 적용
- **아이템 관리**: GUI 목록 (추가/제거). 변경은 다음 사이클부터 반영. 입력 검증: 공백 트림, 빈 문자열·쉼표 포함·중복 거부 (쉼표는 넥슨 API에서 AND 검색 구분자)

## 보안 (넥슨 API 키)

- 저장: `keyring.Set("mabinogi-rice-collector", "nexon-api-key", key)` → Windows 자격 증명 관리자. 디스크 평문 없음
- 첫 실행: `keyring.Get`이 `ErrNotFound` → 설정 다이얼로그 자동 표시(마스킹 입력). 그 외 keyring 오류는 첫 실행으로 오인하지 않고 오류 다이얼로그
- 키 회전: 설정 화면에서 언제든 재입력/삭제 가능. API 401 응답 → 모니터링 중지 + 설정 다이얼로그 유도
- 한계(README 명시): 자격 증명 관리자는 동일 Windows 사용자 경계까지 보호. 기존 사용자에게 구 `.env` 삭제 권고

## 비밀이 아닌 설정

Fyne Preferences (`app.NewWithID("com.github.myeonghan-nim.mabinogi-rice-collector")`, `%APPDATA%\fyne\<id>\preferences.json` 자동 저장):

- `items` (StringList) — 모니터링 아이템 목록
- `intervalSeconds` (Int, 기본 60)

## GUI

- **메인 창**: 아이템 목록(추가 입력창 + 항목별 제거 버튼), 상태 표시(감시 중/중지/키 없음), 감시 시작·중지 토글, 스크롤 로그 뷰(최근 500줄 상한)
- **설정 다이얼로그**: API 키(마스킹), 폴링 주기(초), 저장/취소
- **트레이**: 아이콘 + 메뉴(열기/종료). 창 닫기(X) → 창 숨김, 감시는 지속. 종료는 트레이 메뉴에서
- **알림**: 특가 시 `SendNotification` 토스트 + 로그 뷰에 🚨 항목
- 감시는 키와 아이템이 있으면 앱 시작 시 자동 시작
- 폴링 고루틴에서의 UI 갱신은 전부 `fyne.Do()`로 래핑
- `-H windowsgui`로 콘솔이 없으므로 로그는 `%APPDATA%\mabinogi-rice-collector\app.log`(세션마다 새로 씀) + 인앱 로그 뷰에 동시 기록

## CI/CD

단일 릴리스 워크플로(main 푸시). 태그/릴리스를 분리하면 `GITHUB_TOKEN`이 만든 태그가 워크플로를 트리거하지 않아 두 번째가 영원히 안 도는 함정이 있으므로 단일 잡으로 구성:

1. `windows-2025` 러너 (gcc 사전 설치 → cgo/Fyne 빌드 무설정), `concurrency: release`, `permissions: contents: write`
2. checkout (`fetch-depth: 0`) → setup-go → `go test ./...`
3. mathieudutour/github-tag-action@v6.2, `default_bump: false` — conventional commit(`feat:`→minor, `fix:`→patch, 본문 `BREAKING CHANGE:` 푸터→major)일 때만 태그. 이 액션의 angular preset은 `feat!:`의 `!` 표기를 파싱하지 못하므로 major는 반드시 푸터로 표기
4. `if: steps.tag.outputs.new_tag != ''` 가드 하에: `go build -trimpath -ldflags "-H windowsgui -s -w -X main.version=${{ steps.tag.outputs.new_version }}"` → SHA-256 체크섬 생성 → action-gh-release로 exe + 체크섬 첨부, 본문은 태그 액션의 changelog 출력

`ci.yml`은 pull_request에서 테스트+빌드만 수행(릴리스 파이프라인의 상시 리허설). dependabot은 `chore` prefix라 릴리스를 만들지 않는다.

버전 절차: 전환 머지 전에 현재 main HEAD에 `v1.0.0` 태그 푸시 → 전환 커밋(머지)을 `feat!:`로 → 태그 액션이 v2.0.0 산출.

## 테스트 전략

`internal/core` 단위 테스트 (httptest 기반, CI Windows 러너에서 전체 패키지 컴파일 겸 검증):

- nexon: 정상 응답 파싱, 부분일치 필터, 정렬, 데이터 2개 미만, 401/429/오류 envelope, 타임아웃
- monitor: 특가 조건 경계값(int64 연산), 중복 제거 상태 전이(성립→알림→가격변동→재알림→해제→재성립), 주기 반영
- format: 콤마 포맷·할인율 골든 테스트, 아이템 이름 검증(쉼표·공백·중복)

GUI는 수동 검증(로컬 fyne-cross Docker 빌드 → Windows에서 실행 확인). 로컬 개발 환경(WSL2)에는 mingw/sudo가 없어 전체 앱 컴파일은 fyne-cross 또는 CI가 담당한다.

## 문서 개편

- README 전면 재작성: 개요 → Releases에서 exe 다운로드(SmartScreen 안내 포함) → 첫 실행(API 키 발급·입력) → GUI 사용법 → 설정 → API 제한(개발 단계 1,000건/일 기준 주기 가이드) → 빌드/개발 가이드(WSL2 fyne-cross, CI) → 라이선스
- 삭제: `main.py`, `requirements.txt`, `pyproject.toml`, `mabinogi.service`
- `.gitignore`: Go용으로 교체하되 `.env` 무시 항목 유지(기존 사용자 보호), `.serena/`·빌드 산출물 추가
- 기존 사용자 마이그레이션 노트: `.env`는 자동 이전되지 않음(GUI 재입력), 구 `.env` 파일 삭제 권고
