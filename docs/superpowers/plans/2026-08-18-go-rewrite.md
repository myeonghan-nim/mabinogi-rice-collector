# 마비노기 쌀 콜렉터 v2 Go 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python Discord 봇을 Windows 11+ 단독 실행 Go GUI 앱(토스트/트레이/인앱 알림)으로 재작성하고, main 푸시 시 자동 태그·빌드·릴리스하는 CI를 붙인다.

**Architecture:** Fyne 미의존 `internal/core`(넥슨 API 클라이언트, 폴링/중복제거 모니터, 포맷/검증)와 루트 `main.go`/`ui.go`(Fyne GUI, keyring, 트레이)로 2층 분리. 설정은 Fyne Preferences, 비밀은 Windows 자격 증명 관리자.

**Tech Stack:** Go 1.24+, Fyne v2.8.0, zalando/go-keyring v0.2.8, go-winres(아이콘), GitHub Actions(windows-2025, mathieudutour/github-tag-action@v6.2, softprops/action-gh-release@v3), 로컬 검증은 fyne-cross Docker 이미지.

**Spec:** docs/superpowers/specs/2026-08-18-go-rewrite-design.md

## Global Constraints

- 모듈 경로 `github.com/myeonghan-nim/mabinogi-rice-collector`, go.mod `go 1.24.0`
- `internal/core`는 fyne을 import하지 않는다 (WSL2에서 GL 헤더 없이 테스트 가능해야 함)
- 특가 조건은 int64 정수 연산 `lowest*10 <= next` (부동소수점 금지)
- 알림 문구: `🚨 <아이템> 특가! 일반 <콤마수> / 최저 <콤마수> / 할인율 <소수1자리>%`
- keyring: service `"mabinogi-rice-collector"`, user `"nexon-api-key"`
- Preferences 키: `"items"`(StringList), `"intervalSeconds"`(Int, 기본 60, 최소 1)
- 로컬에는 mingw/sudo 없음 — 전체 앱 컴파일 검증은 fyne-cross Docker 이미지 또는 CI로만 가능. `go test`/`go vet`은 `./internal/...`만 로컬 실행
- 커밋은 conventional commit(`feat:`/`test:`/`docs:`/`chore:`), main 머지 커밋만 `feat!:`

---

### Task 1: Go 모듈 + format.go (포맷·검증, TDD)

**Files:**
- Create: `go.mod`, `internal/core/format.go`, `internal/core/format_test.go`

**Interfaces:**
- Produces: `core.Comma(n int64) string`, `core.AlertText(item string, next, lowest int64) string`, `core.ValidateItemName(name string, existing []string) (string, error)`

- [ ] **Step 1: 모듈 초기화**

```bash
cd /home/hannim/mabinogi-rice-collector
go mod init github.com/myeonghan-nim/mabinogi-rice-collector
```

- [ ] **Step 2: 실패하는 테스트 작성** — `internal/core/format_test.go`

```go
package core

import "testing"

func TestComma(t *testing.T) {
	cases := map[int64]string{0: "0", 100: "100", 1000: "1,000", 45000: "45,000", 1234567: "1,234,567"}
	for n, want := range cases {
		if got := Comma(n); got != want {
			t.Errorf("Comma(%d) = %q, want %q", n, got, want)
		}
	}
}

func TestAlertText(t *testing.T) {
	// Python: 100*(1-100/1200) = 91.666... → "91.7"
	got := AlertText("마나 허브", 1200, 100)
	want := "🚨 마나 허브 특가! 일반 1,200 / 최저 100 / 할인율 91.7%"
	if got != want {
		t.Errorf("got %q, want %q", got, want)
	}
}

func TestValidateItemName(t *testing.T) {
	if _, err := ValidateItemName("  ", nil); err == nil {
		t.Error("빈 이름 허용됨")
	}
	if _, err := ValidateItemName("숏,소드", nil); err == nil {
		t.Error("쉼표 허용됨")
	}
	if _, err := ValidateItemName("마나 허브", []string{"마나 허브"}); err == nil {
		t.Error("중복 허용됨")
	}
	got, err := ValidateItemName("  마나 허브  ", nil)
	if err != nil || got != "마나 허브" {
		t.Errorf("트림 실패: %q, %v", got, err)
	}
}
```

- [ ] **Step 3: 실패 확인** — `go test ./internal/...` → 컴파일 에러(함수 미정의) 확인

- [ ] **Step 4: 구현** — `internal/core/format.go`

```go
package core

import (
	"errors"
	"fmt"
	"strings"
)

// Comma는 천 단위 콤마를 붙인다 (12345 → "12,345").
func Comma(n int64) string {
	s := fmt.Sprintf("%d", n)
	if n < 0 {
		return "-" + Comma(-n)
	}
	var b strings.Builder
	for i, r := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			b.WriteByte(',')
		}
		b.WriteRune(r)
	}
	return b.String()
}

// AlertText는 특가 알림 문구를 만든다.
func AlertText(item string, next, lowest int64) string {
	discount := 100 * (1 - float64(lowest)/float64(next))
	return fmt.Sprintf("🚨 %s 특가! 일반 %s / 최저 %s / 할인율 %.1f%%", item, Comma(next), Comma(lowest), discount)
}

// ValidateItemName은 모니터링 아이템 이름을 정규화·검증한다.
// 쉼표는 넥슨 API에서 AND 검색 구분자라 금지한다.
func ValidateItemName(name string, existing []string) (string, error) {
	name = strings.TrimSpace(name)
	if name == "" {
		return "", errors.New("아이템 이름을 입력해주세요")
	}
	if strings.Contains(name, ",") {
		return "", errors.New("아이템 이름에 쉼표(,)는 사용할 수 없습니다")
	}
	for _, e := range existing {
		if e == name {
			return "", fmt.Errorf("%s은(는) 이미 모니터링 중입니다", name)
		}
	}
	return name, nil
}
```

- [ ] **Step 5: 통과 확인** — `go test ./internal/...` → PASS
- [ ] **Step 6: 커밋** — `git add go.mod internal/ && git commit -m "feat: add core formatting and validation"`

---

### Task 2: nexon.go (API 클라이언트, TDD)

**Files:**
- Create: `internal/core/nexon.go`, `internal/core/nexon_test.go`

**Interfaces:**
- Produces: `core.Client{APIKey, BaseURL string, HTTP *http.Client}`, `core.NewClient(apiKey string) *Client`, `(*Client).FetchLowestTwo(ctx, keyword) (lowest, next int64, err error)`, `core.ErrUnauthorized`, `core.ErrNotEnoughListings`

- [ ] **Step 1: 실패하는 테스트 작성** — `internal/core/nexon_test.go`

```go
package core

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func newTestClient(handler http.HandlerFunc) (*Client, *httptest.Server) {
	srv := httptest.NewServer(handler)
	c := NewClient("test-key")
	c.BaseURL = srv.URL
	c.HTTP = srv.Client()
	return c, srv
}

func TestFetchLowestTwo(t *testing.T) {
	var gotKey, gotKeyword string
	c, srv := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		gotKey = r.Header.Get("x-nxopen-api-key")
		gotKeyword = r.URL.Query().Get("keyword")
		// 정렬 안 된 응답 + 검색어 미포함 항목 1개 섞기
		w.Write([]byte(`{"auction_item":[
			{"item_display_name":"마나 허브","auction_price_per_unit":1200},
			{"item_display_name":"허브 조각","auction_price_per_unit":1},
			{"item_display_name":"축복받은 마나 허브","auction_price_per_unit":100}]}`))
	})
	defer srv.Close()

	lowest, next, err := c.FetchLowestTwo(context.Background(), "마나 허브")
	if err != nil {
		t.Fatal(err)
	}
	if lowest != 100 || next != 1200 {
		t.Errorf("got (%d, %d), want (100, 1200)", lowest, next)
	}
	if gotKey != "test-key" {
		t.Errorf("API 키 헤더 누락: %q", gotKey)
	}
	if gotKeyword != "마나 허브" {
		t.Errorf("keyword 파라미터: %q", gotKeyword)
	}
}

func TestFetchLowestTwoNotEnough(t *testing.T) {
	c, srv := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"auction_item":[{"item_display_name":"마나 허브","auction_price_per_unit":100}]}`))
	})
	defer srv.Close()
	_, _, err := c.FetchLowestTwo(context.Background(), "마나 허브")
	if !errors.Is(err, ErrNotEnoughListings) {
		t.Errorf("want ErrNotEnoughListings, got %v", err)
	}
}

func TestFetchLowestTwoUnauthorized(t *testing.T) {
	for _, code := range []int{401, 403} {
		c, srv := newTestClient(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(code)
			w.Write([]byte(`{"error":{"name":"OPENAPI00004","message":"invalid key"}}`))
		})
		_, _, err := c.FetchLowestTwo(context.Background(), "x")
		srv.Close()
		if !errors.Is(err, ErrUnauthorized) {
			t.Errorf("status %d: want ErrUnauthorized, got %v", code, err)
		}
	}
}

func TestFetchLowestTwoRateLimited(t *testing.T) {
	c, srv := newTestClient(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(429)
		w.Write([]byte(`{"error":{"name":"OPENAPI00007","message":"rate limited"}}`))
	})
	defer srv.Close()
	_, _, err := c.FetchLowestTwo(context.Background(), "x")
	if err == nil || !strings.Contains(err.Error(), "OPENAPI00007") {
		t.Errorf("429 에러에 API 에러명 미포함: %v", err)
	}
}
```

(파일 상단 import에 `"strings"` 포함.)

- [ ] **Step 2: 실패 확인** — `go test ./internal/...` → 컴파일 에러 확인
- [ ] **Step 3: 구현** — `internal/core/nexon.go`

```go
package core

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"time"
)

const apiEndpoint = "https://open.api.nexon.com/mabinogi/v1/auction/keyword-search"

var (
	ErrUnauthorized      = errors.New("API 키 인증 실패")
	ErrNotEnoughListings = errors.New("경매장 데이터 부족")
)

// Client는 넥슨 Open API 클라이언트다.
type Client struct {
	APIKey  string
	BaseURL string
	HTTP    *http.Client
}

func NewClient(apiKey string) *Client {
	return &Client{
		APIKey:  apiKey,
		BaseURL: apiEndpoint,
		HTTP:    &http.Client{Timeout: 10 * time.Second},
	}
}

type auctionItem struct {
	ItemDisplayName     string `json:"item_display_name"`
	AuctionPricePerUnit int64  `json:"auction_price_per_unit"`
}

type searchResponse struct {
	AuctionItem []auctionItem `json:"auction_item"`
	Error       *struct {
		Name    string `json:"name"`
		Message string `json:"message"`
	} `json:"error"`
}

// FetchLowestTwo는 표시 이름에 검색어가 포함된 매물 중 최저가와 차순위가를 돌려준다.
// Python 원본과 동일하게 첫 응답 페이지만 사용한다.
func (c *Client) FetchLowestTwo(ctx context.Context, keyword string) (lowest, next int64, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		c.BaseURL+"?"+url.Values{"keyword": {keyword}}.Encode(), nil)
	if err != nil {
		return 0, 0, err
	}
	req.Header.Set("accept", "application/json")
	req.Header.Set("x-nxopen-api-key", c.APIKey)

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return 0, 0, err
	}
	defer resp.Body.Close()

	var body searchResponse
	decodeErr := json.NewDecoder(resp.Body).Decode(&body)

	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		return 0, 0, ErrUnauthorized
	}
	if resp.StatusCode != http.StatusOK {
		msg := ""
		if body.Error != nil {
			msg = " " + body.Error.Name + ": " + body.Error.Message
		}
		return 0, 0, fmt.Errorf("API 요청 실패: %d%s", resp.StatusCode, msg)
	}
	if decodeErr != nil {
		return 0, 0, fmt.Errorf("응답 파싱 실패: %w", decodeErr)
	}

	items := body.AuctionItem
	sort.Slice(items, func(i, j int) bool {
		return items[i].AuctionPricePerUnit < items[j].AuctionPricePerUnit
	})
	prices := make([]int64, 0, 2)
	for _, it := range items {
		if strings.Contains(it.ItemDisplayName, keyword) {
			prices = append(prices, it.AuctionPricePerUnit)
			if len(prices) == 2 {
				break
			}
		}
	}
	if len(prices) < 2 {
		return 0, 0, fmt.Errorf("%w: %d개 발견 (2개 필요)", ErrNotEnoughListings, len(prices))
	}
	return prices[0], prices[1], nil
}
```

- [ ] **Step 4: 통과 확인** — `go test ./internal/...` → PASS
- [ ] **Step 5: 커밋** — `git add internal/ && git commit -m "feat: add Nexon auction API client"`

---

### Task 3: monitor.go (폴링 루프 + 중복 제거, TDD)

**Files:**
- Create: `internal/core/monitor.go`, `internal/core/monitor_test.go`

**Interfaces:**
- Consumes: `Fetcher` 인터페이스로 Task 2의 `*Client` 사용, Task 1의 `Comma`
- Produces: `core.IsBargain(lowest, next int64) bool`, `core.Monitor{Fetch Fetcher, Items func() []string, Interval func() time.Duration, OnLog func(string), OnAlert func(item string, next, lowest int64), OnAuthError func()}`, `(*Monitor).Run(ctx)`

- [ ] **Step 1: 실패하는 테스트 작성** — `internal/core/monitor_test.go`

```go
package core

import (
	"context"
	"testing"
	"time"
)

func TestIsBargain(t *testing.T) {
	cases := []struct {
		lowest, next int64
		want         bool
	}{
		{1, 10, true},    // 10% 정확히
		{2, 10, false},   // 초과
		{15, 150, true},  // Python: 15 <= 15.0 (경계 포함)
		{16, 150, false},
		{100, 45000, true},
	}
	for _, c := range cases {
		if got := IsBargain(c.lowest, c.next); got != c.want {
			t.Errorf("IsBargain(%d, %d) = %v, want %v", c.lowest, c.next, got, c.want)
		}
	}
}

// fakeFetcher는 호출마다 미리 정한 가격을 차례로 돌려준다.
type fakeFetcher struct {
	seq []([2]int64)
	i   int
	err error
}

func (f *fakeFetcher) FetchLowestTwo(ctx context.Context, keyword string) (int64, int64, error) {
	if f.err != nil {
		return 0, 0, f.err
	}
	p := f.seq[f.i%len(f.seq)]
	f.i++
	return p[0], p[1], nil
}

func newTestMonitor(f Fetcher) (*Monitor, *[]string) {
	alerts := &[]string{}
	m := &Monitor{
		Fetch:    f,
		Items:    func() []string { return []string{"마나 허브"} },
		Interval: func() time.Duration { return time.Hour },
		OnLog:    func(string) {},
		OnAlert: func(item string, next, lowest int64) {
			*alerts = append(*alerts, AlertText(item, next, lowest))
		},
	}
	m.lastAlerted = map[string]int64{}
	return m, alerts
}

func TestMonitorDedup(t *testing.T) {
	// 사이클: 특가(100) → 같은 가격 유지 → 가격 변동(90) → 특가 해제 → 같은 가격 재등장(90)
	f := &fakeFetcher{seq: [][2]int64{{100, 45000}, {100, 45000}, {90, 45000}, {40000, 45000}, {90, 45000}}}
	m, alerts := newTestMonitor(f)
	for i := 0; i < 5; i++ {
		m.cycle(context.Background())
	}
	// 기대: 1번째(신규), 3번째(가격 변동), 5번째(해제 후 재등장) = 총 3회
	if len(*alerts) != 3 {
		t.Errorf("알림 %d회, want 3회: %v", len(*alerts), *alerts)
	}
}

func TestMonitorAuthErrorStopsCycle(t *testing.T) {
	f := &fakeFetcher{err: ErrUnauthorized}
	m, _ := newTestMonitor(f)
	called := false
	m.OnAuthError = func() { called = true }
	m.cycle(context.Background())
	if !called {
		t.Error("OnAuthError 미호출")
	}
}

func TestMonitorRunStopsOnCancel(t *testing.T) {
	f := &fakeFetcher{seq: [][2]int64{{40000, 45000}}}
	m, _ := newTestMonitor(f)
	m.Interval = func() time.Duration { return time.Millisecond }
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() { m.Run(ctx); close(done) }()
	time.Sleep(10 * time.Millisecond)
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("Run이 취소 후에도 종료되지 않음")
	}
}
```

- [ ] **Step 2: 실패 확인** — `go test ./internal/...` → 컴파일 에러 확인
- [ ] **Step 3: 구현** — `internal/core/monitor.go`

```go
package core

import (
	"context"
	"errors"
	"time"
)

// IsBargain은 특가 조건(최저가 ≤ 차순위가의 10%)을 정수 연산으로 판정한다.
func IsBargain(lowest, next int64) bool {
	return lowest*10 <= next
}

// Fetcher는 아이템의 (최저가, 차순위가)를 가져온다. *Client가 구현한다.
type Fetcher interface {
	FetchLowestTwo(ctx context.Context, keyword string) (lowest, next int64, err error)
}

// Monitor는 주기적으로 가격을 조회하고 중복 없이 알림을 발생시킨다.
// 콜백은 모두 Run 고루틴에서 호출된다 — UI 갱신은 호출자가 fyne.Do로 감쌀 것.
type Monitor struct {
	Fetch       Fetcher
	Items       func() []string      // 매 사이클 호출 (GUI 편집은 다음 사이클부터 반영)
	Interval    func() time.Duration // 매 사이클 호출 (설정 변경 즉시 반영)
	OnLog       func(msg string)
	OnAlert     func(item string, next, lowest int64)
	OnAuthError func() // 401/403 — 호출자가 감시를 중단해야 한다

	lastAlerted map[string]int64 // 아이템 → 마지막으로 알린 최저가
}

// Run은 ctx 취소까지 블로킹한다. 작업 후 대기 방식이라 사이클이 주기보다
// 오래 걸려도 API를 연달아 치지 않는다.
func (m *Monitor) Run(ctx context.Context) {
	m.lastAlerted = map[string]int64{}
	for {
		m.cycle(ctx)
		select {
		case <-ctx.Done():
			return
		case <-time.After(m.Interval()):
		}
	}
}

func (m *Monitor) cycle(ctx context.Context) {
	for _, item := range m.Items() {
		if ctx.Err() != nil {
			return
		}
		lowest, next, err := m.Fetch.FetchLowestTwo(ctx, item)
		if errors.Is(err, ErrUnauthorized) {
			m.OnLog("API 키 인증 실패 — 설정에서 키를 확인해주세요")
			if m.OnAuthError != nil {
				m.OnAuthError()
			}
			return
		}
		if err != nil {
			m.OnLog(item + " 조회 실패: " + err.Error())
			continue
		}
		m.OnLog(item + " → 일반: " + Comma(next) + ", 최저: " + Comma(lowest))
		m.checkAlert(item, lowest, next)
	}
}

func (m *Monitor) checkAlert(item string, lowest, next int64) {
	if !IsBargain(lowest, next) {
		delete(m.lastAlerted, item) // 특가 해제 → 재무장
		return
	}
	if last, ok := m.lastAlerted[item]; ok && last == lowest {
		return // 같은 특가 유지 중 — 중복 알림 방지
	}
	m.lastAlerted[item] = lowest
	m.OnAlert(item, next, lowest)
}
```

- [ ] **Step 4: 통과 확인** — `go test ./internal/...` → PASS (`-race` 포함 1회)
- [ ] **Step 5: 커밋** — `git add internal/ && git commit -m "feat: add polling monitor with alert dedup"`

---

### Task 4: GUI (main.go, ui.go, 아이콘)

**Files:**
- Create: `main.go`, `ui.go`, `winres/icon.png`(생성), `winres/winres.json`, `rsrc_windows_amd64.syso`(go-winres 산출물, 커밋)

**Interfaces:**
- Consumes: Task 1–3의 `core.NewClient`, `core.Monitor`, `core.AlertText`, `core.ValidateItemName`
- Produces: 실행 가능한 Fyne 앱. `var version = "dev"`(빌드 시 `-X main.version=` 주입)

- [ ] **Step 1: 의존성 추가**

```bash
go get fyne.io/fyne/v2@v2.8.0 github.com/zalando/go-keyring@v0.2.8
```

- [ ] **Step 2: 아이콘 생성** — 스크래치패드에 단순 아이콘(쌀그릇 모티프, 256×256 PNG) 생성 스크립트를 작성·실행해 `winres/icon.png` 저장. 표준 라이브러리 image/png만 사용.

- [ ] **Step 3: main.go 작성**

```go
package main

import (
	_ "embed"
	"io"
	"log"
	"os"
	"path/filepath"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
)

//go:embed winres/icon.png
var iconPNG []byte

var version = "dev" // 빌드 시 -ldflags "-X main.version=..." 주입

func main() {
	if f := setupLogFile(); f != nil {
		defer f.Close()
	}
	a := app.NewWithID("com.github.myeonghan-nim.mabinogi-rice-collector")
	a.SetIcon(fyne.NewStaticResource("icon.png", iconPNG))
	newUI(a).run()
}

// -H windowsgui 빌드는 콘솔이 없으므로 로그를 %APPDATA% 파일에도 남긴다.
func setupLogFile() *os.File {
	dir, err := os.UserConfigDir()
	if err != nil {
		return nil
	}
	dir = filepath.Join(dir, "mabinogi-rice-collector")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil
	}
	f, err := os.Create(filepath.Join(dir, "app.log")) // ponytail: 세션마다 새로 씀, 로테이션은 필요해지면
	if err != nil {
		return nil
	}
	log.SetOutput(io.MultiWriter(os.Stderr, f))
	return f
}
```

- [ ] **Step 4: ui.go 작성**

```go
package main

import (
	"context"
	"errors"
	"log"
	"strconv"
	"strings"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/driver/desktop"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/widget"
	"github.com/zalando/go-keyring"

	"github.com/myeonghan-nim/mabinogi-rice-collector/internal/core"
)

const (
	keyringService  = "mabinogi-rice-collector"
	keyringUser     = "nexon-api-key"
	prefItems       = "items"
	prefInterval    = "intervalSeconds"
	defaultInterval = 60
	maxLogLines     = 500
)

type ui struct {
	app      fyne.App
	win      fyne.Window
	status   *widget.Label
	toggle   *widget.Button
	list     *widget.List
	logLabel *widget.Label
	logView  *container.Scroll
	logLines []string
	items    []string

	cancel context.CancelFunc // nil이면 감시 중지 상태
}

func newUI(a fyne.App) *ui {
	u := &ui{app: a}
	u.win = a.NewWindow("마비노기 쌀 콜렉터 " + version)
	u.items = a.Preferences().StringListWithFallback(prefItems, nil)

	u.status = widget.NewLabel("상태: 중지됨")
	u.toggle = widget.NewButton("감시 시작", u.toggleMonitoring)
	settingsBtn := widget.NewButton("설정", func() { u.showSettings(false) })

	addEntry := widget.NewEntry()
	addEntry.PlaceHolder = "모니터링할 아이템 이름"
	addBtn := widget.NewButton("추가", func() {
		u.addItem(addEntry.Text)
		addEntry.SetText("")
	})
	addEntry.OnSubmitted = func(s string) {
		u.addItem(s)
		addEntry.SetText("")
	}

	u.list = widget.NewList(
		func() int { return len(u.items) },
		func() fyne.CanvasObject {
			return container.NewBorder(nil, nil, nil, widget.NewButton("제거", nil), widget.NewLabel(""))
		},
		func(i widget.ListItemID, o fyne.CanvasObject) {
			row := o.(*fyne.Container)
			row.Objects[0].(*widget.Label).SetText(u.items[i])
			name := u.items[i]
			row.Objects[1].(*widget.Button).OnTapped = func() { u.removeItem(name) }
		},
	)

	u.logLabel = widget.NewLabel("")
	u.logLabel.Wrapping = fyne.TextWrapWord
	u.logView = container.NewScroll(u.logLabel)

	topBar := container.NewHBox(u.status, layout.NewSpacer(), u.toggle, settingsBtn)
	itemsPanel := container.NewBorder(container.NewBorder(nil, nil, nil, addBtn, addEntry), nil, nil, nil, u.list)
	split := container.NewHSplit(itemsPanel, u.logView)
	split.SetOffset(0.4)
	u.win.SetContent(container.NewBorder(topBar, nil, nil, nil, split))
	u.win.Resize(fyne.NewSize(720, 460))

	u.setupTray()
	return u
}

func (u *ui) run() {
	_, err := keyring.Get(keyringService, keyringUser)
	switch {
	case errors.Is(err, keyring.ErrNotFound):
		u.appendLog("첫 실행입니다 — 넥슨 API 키를 입력해주세요")
		u.showSettings(true)
	case err != nil:
		dialog.ShowError(errors.New("자격 증명 관리자 오류: "+err.Error()), u.win)
	default:
		u.startMonitoring()
	}
	u.win.ShowAndRun()
}

// 창 닫기(X)는 숨김 처리하고 감시는 트레이에서 계속된다. 종료는 트레이 메뉴로.
func (u *ui) setupTray() {
	desk, ok := u.app.(desktop.App)
	if !ok {
		return
	}
	desk.SetSystemTrayMenu(fyne.NewMenu("마비노기 쌀 콜렉터",
		fyne.NewMenuItem("열기", func() { u.win.Show() }),
	))
	u.win.SetCloseIntercept(func() { u.win.Hide() })
}

func (u *ui) toggleMonitoring() {
	if u.cancel != nil {
		u.stopMonitoring()
	} else {
		u.startMonitoring()
	}
}

func (u *ui) startMonitoring() {
	if u.cancel != nil {
		return
	}
	key, err := keyring.Get(keyringService, keyringUser)
	if err != nil {
		u.appendLog("API 키가 없습니다 — 설정에서 입력해주세요")
		u.showSettings(true)
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	u.cancel = cancel
	mon := &core.Monitor{
		Fetch: core.NewClient(key),
		Items: func() []string {
			return u.app.Preferences().StringListWithFallback(prefItems, nil)
		},
		Interval: func() time.Duration {
			return time.Duration(u.app.Preferences().IntWithFallback(prefInterval, defaultInterval)) * time.Second
		},
		OnLog: func(msg string) {
			fyne.Do(func() { u.appendLog(msg) })
		},
		OnAlert: func(item string, next, lowest int64) {
			text := core.AlertText(item, next, lowest)
			u.app.SendNotification(fyne.NewNotification("마비노기 쌀 콜렉터", text))
			fyne.Do(func() { u.appendLog(text) })
		},
		OnAuthError: func() {
			fyne.Do(func() {
				u.stopMonitoring()
				u.showSettings(true)
			})
		},
	}
	go mon.Run(ctx)
	u.status.SetText("상태: 감시 중")
	u.toggle.SetText("감시 중지")
	u.appendLog("가격 감시 시작")
}

func (u *ui) stopMonitoring() {
	if u.cancel == nil {
		return
	}
	u.cancel()
	u.cancel = nil
	u.status.SetText("상태: 중지됨")
	u.toggle.SetText("감시 시작")
	u.appendLog("가격 감시 중지")
}

func (u *ui) addItem(name string) {
	name, err := core.ValidateItemName(name, u.items)
	if err != nil {
		dialog.ShowError(err, u.win)
		return
	}
	u.items = append(u.items, name)
	u.app.Preferences().SetStringList(prefItems, u.items)
	u.list.Refresh()
	u.appendLog(name + " 추가됨")
}

func (u *ui) removeItem(name string) {
	kept := u.items[:0]
	for _, it := range u.items {
		if it != name {
			kept = append(kept, it)
		}
	}
	u.items = kept
	u.app.Preferences().SetStringList(prefItems, u.items)
	u.list.Refresh()
	u.appendLog(name + " 제거됨")
}

// restartIfRunning: 설정 저장 후 새 키/주기를 반영한다.
func (u *ui) restartIfRunning() {
	if u.cancel != nil {
		u.stopMonitoring()
		u.startMonitoring()
	}
}

func (u *ui) showSettings(startAfterSave bool) {
	keyEntry := widget.NewPasswordEntry()
	if _, err := keyring.Get(keyringService, keyringUser); err == nil {
		keyEntry.PlaceHolder = "(저장됨 — 변경할 때만 입력)"
	}
	intervalEntry := widget.NewEntry()
	intervalEntry.SetText(strconv.Itoa(u.app.Preferences().IntWithFallback(prefInterval, defaultInterval)))

	d := dialog.NewForm("설정", "저장", "취소", []*widget.FormItem{
		widget.NewFormItem("넥슨 API 키", keyEntry),
		widget.NewFormItem("폴링 주기(초)", intervalEntry),
	}, func(ok bool) {
		if !ok {
			return
		}
		if v := strings.TrimSpace(keyEntry.Text); v != "" {
			if err := keyring.Set(keyringService, keyringUser, v); err != nil {
				dialog.ShowError(errors.New("키 저장 실패: "+err.Error()), u.win)
				return
			}
			u.appendLog("API 키 저장됨 (Windows 자격 증명 관리자)")
		}
		n, err := strconv.Atoi(strings.TrimSpace(intervalEntry.Text))
		if err != nil || n < 1 {
			dialog.ShowError(errors.New("폴링 주기는 1 이상의 정수여야 합니다"), u.win)
			return
		}
		u.app.Preferences().SetInt(prefInterval, n)
		if startAfterSave && u.cancel == nil {
			u.startMonitoring()
		} else {
			u.restartIfRunning()
		}
	}, u.win)
	d.Resize(fyne.NewSize(440, 0))
	d.Show()
}

func (u *ui) appendLog(msg string) {
	line := time.Now().Format("15:04:05") + " " + msg
	log.Println(msg) // 파일 로그
	u.logLines = append(u.logLines, line)
	if len(u.logLines) > maxLogLines {
		u.logLines = u.logLines[len(u.logLines)-maxLogLines:]
	}
	u.logLabel.SetText(strings.Join(u.logLines, "\n"))
	u.logView.ScrollToBottom()
}
```

- [ ] **Step 5: winres 리소스 생성** — `winres/winres.json`:

```json
{
  "RT_GROUP_ICON": {
    "APP": {
      "0000": ["icon.png"]
    }
  },
  "RT_MANIFEST": {
    "#1": {
      "0409": {
        "identity": {"name": "mabinogi-rice-collector", "version": "2.0.0.0"},
        "execution-level": "asInvoker",
        "dpi-awareness": "per monitor v2"
      }
    }
  }
}
```

실행: `go run github.com/tc-hib/go-winres@latest make --in winres/winres.json --arch amd64` → `rsrc_windows_amd64.syso` 커밋 (Windows 빌드에만 링크됨, 리눅스 테스트에 영향 없음).

- [ ] **Step 6: 로컬 검증** — `go vet ./internal/...`, `go test ./internal/...` PASS 확인 후 fyne-cross Docker 이미지로 Windows exe 컴파일:

```bash
docker run --rm -v "$PWD":/app -w /app \
  -e CGO_ENABLED=1 -e GOOS=windows -e GOARCH=amd64 -e CC=x86_64-w64-mingw32-gcc \
  fyneio/fyne-cross-images:windows \
  go build -trimpath -ldflags "-H windowsgui -s -w" -o mabinogi-rice-collector.exe .
```

Expected: `mabinogi-rice-collector.exe` 생성 (컴파일 성공 = ui.go/main.go 타입 검증 완료).

- [ ] **Step 7: 커밋** — `git add main.go ui.go winres/ rsrc_windows_amd64.syso go.mod go.sum && git commit -m "feat: add Fyne GUI with tray, toast alerts and keyring settings"`

---

### Task 5: CI/CD + dependabot

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/dependabot.yml`

**Interfaces:**
- Consumes: Task 4까지의 빌드 가능한 루트 패키지, `main.version` ldflags 주입점

- [ ] **Step 1: ci.yml** (PR 검증 + 릴리스 파이프라인 리허설)

```yaml
name: ci

on:
  pull_request:
  workflow_dispatch:

jobs:
  test-build:
    runs-on: windows-2025
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-go@v7
        with:
          go-version: stable
      - run: go vet ./...
      - run: go test ./...
      - name: Build
        env:
          CGO_ENABLED: "1"
        run: go build -trimpath -ldflags "-H windowsgui -s -w -X main.version=ci" -o mabinogi-rice-collector.exe .
```

- [ ] **Step 2: release.yml** (main 푸시 → 태그 → 빌드 → 릴리스, 단일 워크플로)

```yaml
name: release

on:
  push:
    branches: [main]

permissions:
  contents: write

concurrency: release

jobs:
  release:
    runs-on: windows-2025
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: actions/setup-go@v7
        with:
          go-version: stable
      - run: go test ./...
      - name: Bump version and push tag
        id: tag
        uses: mathieudutour/github-tag-action@v6.2
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          default_bump: false
      - name: Build
        if: steps.tag.outputs.new_tag != ''
        env:
          CGO_ENABLED: "1"
        run: go build -trimpath -ldflags "-H windowsgui -s -w -X main.version=${{ steps.tag.outputs.new_version }}" -o mabinogi-rice-collector.exe .
      - name: Checksum
        if: steps.tag.outputs.new_tag != ''
        shell: pwsh
        run: '"{0}  mabinogi-rice-collector.exe" -f (Get-FileHash mabinogi-rice-collector.exe -Algorithm SHA256).Hash | Out-File -Encoding ascii SHA256SUMS.txt'
      - name: Create release
        if: steps.tag.outputs.new_tag != ''
        uses: softprops/action-gh-release@v3
        with:
          tag_name: ${{ steps.tag.outputs.new_tag }}
          body: ${{ steps.tag.outputs.changelog }}
          files: |
            mabinogi-rice-collector.exe
            SHA256SUMS.txt
```

- [ ] **Step 3: dependabot.yml** (`chore` prefix → conventional commit 미해당 → 릴리스 미발생)

```yaml
version: 2
updates:
  - package-ecosystem: gomod
    directory: /
    schedule:
      interval: weekly
    commit-message:
      prefix: chore
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    commit-message:
      prefix: chore
```

- [ ] **Step 4: YAML 문법 검증** — `python3 -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/**/*.yml', recursive=True)]"` (또는 동등한 파서)
- [ ] **Step 5: 커밋** — `git add .github/ && git commit -m "feat: add release pipeline and CI"`

---

### Task 6: Python 제거 + .gitignore + README 개정

**Files:**
- Delete: `main.py`, `requirements.txt`, `pyproject.toml`, `mabinogi.service`
- Modify: `.gitignore`(전면 교체), `README.md`(전면 재작성)

- [ ] **Step 1: Python 파일 삭제** — `git rm main.py requirements.txt pyproject.toml mabinogi.service`
- [ ] **Step 2: .gitignore 교체** — Go용 최소 구성. **`.env` 무시 항목은 유지**(v1 사용자의 기존 `.env` 오커밋 방지):

```gitignore
# v1 시절 비밀 파일 — 기존 사용자 보호를 위해 유지
.env
.env.*

# 빌드 산출물
*.exe
SHA256SUMS.txt
fyne-cross/

# 로그
*.log

# 도구
.serena/
.vscode/
.idea/

# OS
Thumbs.db
[Dd]esktop.ini
.DS_Store
```

- [ ] **Step 3: README.md 전면 재작성** — 구성(전부 한국어, 기존 톤 유지):
  1. 개요: Windows 11+ 단독 실행 GUI 앱, 넥슨 Open API 경매장 감시, 특가 시 토스트/트레이/인앱 알림. v1(Python/Discord)에서 전환됨 명시
  2. 설치: Releases에서 `mabinogi-rice-collector.exe` 다운로드, SHA-256 확인 방법, SmartScreen "추가 정보 → 실행" 안내(서명 없음, 이유 한 줄)
  3. 첫 실행: 넥슨 개발자센터 API 키 발급 절차(기존 내용 재사용), 설정 다이얼로그에 입력 → Windows 자격 증명 관리자에 저장됨(평문 파일 없음, 동일 사용자 경계 한계 명시)
  4. 사용법: 아이템 추가/제거, 감시 시작/중지, 로그 뷰, 창 닫기 = 트레이 최소화, 종료는 트레이 메뉴
  5. 설정: 폴링 주기(기본 60초), API 제한표(개발 단계 5건/초·1,000건/일 → 주기 가이드: 아이템 수 × 86,400/주기 ≤ 1,000), 429 대처
  6. 특가 판정 원리: 최저가 ≤ 차순위가 × 10%, 중복 알림 방지 규칙
  7. v1에서 마이그레이션: Discord 봇·명령어 제거됨, `.env` 자동 이전 없음(GUI 재입력), 구 `.env` 삭제 권고
  8. 개발/빌드: `go test ./internal/...`, WSL2에선 fyne-cross Docker로 Windows exe 빌드(명령 포함), CI가 main 푸시마다 태그·릴리스(conventional commit 규칙 설명)
  9. 라이선스: Apache-2.0 유지
- [ ] **Step 4: 링크·잔재 검사** — `grep -ri -l "python\|discord\|systemd\|uv \|\.env" README.md` 결과가 의도된 언급(마이그레이션 절)뿐인지 확인
- [ ] **Step 5: 커밋** — `git add -A && git commit -m "feat!: replace Python Discord bot with Go GUI app

BREAKING CHANGE: Discord 봇과 명령어를 제거하고 Windows GUI 앱으로 전환"`

---

### Task 7: 최종 검증 + 리뷰

- [ ] **Step 1:** `go vet ./internal/...` + `go test -race ./internal/...` 전체 PASS
- [ ] **Step 2:** fyne-cross Docker 빌드 재실행 → exe 생성 확인 (Task 4 Step 6과 동일 명령)
- [ ] **Step 3:** 다중 에이전트 적대적 코드 리뷰(버그/스펙 불일치/단순화) → 확인된 결함 수정 → 테스트 재실행
- [ ] **Step 4:** 스펙 대비 최종 점검(스펙의 각 절이 코드/문서에 반영됐는지) 후 필요 시 커밋

---

## 통합 절차 (구현 완료 후, 사용자 확인 필요)

1. 현재 main HEAD(`e3b6011`)에 `v1.0.0` 태그 푸시 (버전 연속성 — pyproject 1.0.0 계승)
2. `feat/go-rewrite` 브랜치 푸시 → PR 생성(ci.yml 리허설 실행됨) → 머지 커밋/스쿼시 제목을 `feat!:`로
3. main 푸시 시 release.yml이 v2.0.0 태그 + exe/체크섬 릴리스 생성
4. Windows에서 exe 실제 실행 검증(GUI·토스트·트레이·자격 증명 저장)은 사용자만 가능 — 릴리스 후 확인 요청
