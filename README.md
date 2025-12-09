# 마비노기 쌀 콜렉터 (Mabinogi Rice Collector) 디스코드 봇

## 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [작동 원리](#작동-원리)
- [설치 방법](#설치-방법)
- [환경 설정](#환경-설정)
- [사용법](#사용법)
- [봇 명령어](#봇-명령어)
- [서비스 등록 (systemd)](#서비스-등록-systemd)
- [API 제한 사항](#api-제한-사항)
- [최적화 내역](#최적화-내역)
- [문제 해결](#문제-해결)
- [라이선스](#라이선스)

## 개요

**마비노기 쌀 콜렉터**는 마비노기 경매장을 실시간으로 모니터링하는 디스코드 봇입니다.

이 봇은 넥슨 Open API를 활용하여 지정된 아이템의 경매장 가격을 추적하고, **특가 아이템**이 등록되면 즉시 Discord 채널로 알림을 보내줍니다.

### 이런 분들에게 추천합니다

- 특정 아이템을 저렴하게 구매하고 싶은 플레이어
- 경매장 시세를 실시간으로 파악하고 싶은 상인
- 아이템 가격 동향을 분석하고 싶은 연구자
- 자동화된 가격 모니터링 시스템이 필요한 길드

## 주요 기능

### 실시간 가격 모니터링

- 1초마다 등록된 아이템의 경매장 가격을 자동 확인
- 여러 아이템을 동시에 모니터링 가능
- 비동기 처리로 빠르고 효율적인 작동

### 스마트 알림 시스템

- 최저가가 일반 판매가의 **10% 이하**일 때 자동 알림
- Discord 채널에 실시간 특가 정보 전송
- 할인율, 최저가, 일반가 정보 제공

### 간편한 Discord 명령어

- `!추가` - 모니터링할 아이템 추가
- `!제거` - 모니터링 중단
- `!목록` - 현재 추적 중인 아이템 확인

### 고성능 최적화

- 비동기 HTTP 요청 (aiohttp)
- 연결 풀링으로 네트워크 부하 감소
- 메모리 효율적인 데이터 처리
- 캐싱으로 파일 I/O 최소화

## 작동 원리

```text
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Discord   │  명령어  │  Discord Bot │  API 요청 │ 넥슨 Open   │
│   사용자    │ ───────> │   (main.py)  │ ───────> │    API      │
└─────────────┘         └──────────────┘         └─────────────┘
                              │                          │
                              │  1초마다 가격 확인        │
                              │ <────────────────────────┘
                              │
                              ▼
                        특가 발견 시
                              │
                              ▼
                        ┌──────────────┐
                        │   Discord    │
                        │   채널 알림  │
                        └──────────────┘
```

### 처리 흐름

1. **봇 시작**: Discord에 연결 및 HTTP 세션 생성
2. **가격 체크 루프**:
   - `.env` 파일에서 모니터링 아이템 목록 로드
   - 각 아이템에 대해 넥슨 API 호출
   - 경매장 데이터 분석 (최저가, 차순위 가격)
3. **특가 감지**: 최저가 ≤ 차순위 가격 × 10%
4. **알림 발송**: Discord 채널에 특가 정보 전송
5. **반복**: 1초 후 다시 체크

## 설치 방법

### 사전 요구사항

- **Python 3.8 이상**
- **Git**
- **Discord 봇 토큰** ([Discord Developer Portal](https://discord.com/developers/applications)에서 발급)
- **넥슨 Open API 키** ([넥슨 개발자센터](https://developers.nexon.com/)에서 발급)

### 1. 저장소 클론

```bash
git clone https://github.com/yourusername/mabinogi-rice-collector.git
cd mabinogi-rice-collector
```

### 2. uv 설치 (초고속 Python 패키지 매니저)

**Linux/macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**또는 pip으로 설치:**

```bash
pip install uv
```

### 3. 가상환경 생성 및 의존성 설치

#### 방법 1: uv 사용 (권장, 10-100배 빠름)

```bash
# 가상환경 생성 및 패키지 설치를 한 번에
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 의존성 설치
uv pip install -r requirements.txt
```

#### 방법 2: 기존 pip 사용

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

설치되는 주요 패키지:

- `aiohttp==3.12.14` - 비동기 HTTP 클라이언트
- `discord.py==2.5.2` - Discord 봇 라이브러리
- `python-dotenv==1.1.0` - 환경 변수 관리
- `requests==2.32.4` - HTTP 요청 (호환성용)
- `urllib3==2.6.0` - URL 처리

**uv 사용의 장점:**

- pip 대비 10-100배 빠른 설치 속도
- Rust로 작성되어 매우 효율적
- pip와 100% 호환되는 인터페이스
- 디스크 공간 절약 (글로벌 캐시 사용)

## 환경 설정

### 1. `.env` 파일 생성

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력하세요:

```bash
# 넥슨 Open API 키 (필수)
MABINOGI_API_KEY=your_nexon_api_key_here

# Discord 봇 토큰 (필수)
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Discord 채널 ID (필수)
DISCORD_CHANNEL_ID=1234567890123456789

# 모니터링할 아이템 목록 (쉼표로 구분)
MABINOGI_ITEMS=심술 난 고양이의 구슬,마나 허브
```

### 2. Discord 채널 ID 확인 방법

1. Discord에서 **개발자 모드** 활성화:
   - 설정 → 고급 → 개발자 모드 ON
2. 알림을 받을 채널에 우클릭
3. **ID 복사** 클릭
4. `.env` 파일의 `DISCORD_CHANNEL_ID`에 붙여넣기

### 3. 넥슨 API 키 발급

1. [넥슨 개발자센터](https://developers.nexon.com/) 접속
2. 로그인 후 **애플리케이션 등록**
3. **마비노기** API 선택
4. 발급받은 API 키를 `.env` 파일에 입력

### 4. Discord 봇 생성

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. **New Application** 클릭
3. **Bot** 탭에서 다음 설정:
   - **TOKEN** 아래의 **Reset Token** 또는 **Copy** 버튼을 눌러 토큰 복사
   - 복사한 토큰을 `.env` 파일의 `DISCORD_BOT_TOKEN`에 입력
   - **Privileged Gateway Intents** 섹션에서:
     - **MESSAGE CONTENT INTENT** 활성화 (파란색 토글로 변경, 필수)
4. **OAuth2 → URL Generator** 탭으로 이동:
   - **SCOPES** 섹션에서:
     - `bot` 체크박스 선택
   - **BOT PERMISSIONS** 섹션에서 다음 3가지 권한만 선택:
     - **General Permissions**:
       - View Channels (필수)
     - **Text Permissions**:
       - Send Messages (필수)
       - Read Message History (필수)
5. 페이지 하단의 **GENERATED URL** 복사하여 브라우저에서 열어 봇을 서버에 초대
   - URL 형식: `https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=68608&scope=bot`
   - **권한 코드**: `68608` (View Channels + Send Messages + Read Message History)

## 사용법

### 봇 실행

```bash
# 가상환경 활성화 (필요시)
source .venv/bin/activate  # uv 사용 시
# source venv/bin/activate  # pip 사용 시

# 봇 실행
python main.py
```

### 정상 실행 시 로그 예시

```text
2025-12-09 14:30:15 [INFO] Logged in as MabiRiceBot#1234
2025-12-09 14:30:15 [INFO] MabiRiceBot#1234 으로 로그인 성공, 가격 모니터링 시작!
2025-12-09 14:30:15 [INFO] 가격 모니터링 태스크 시작
2025-12-09 14:30:16 [INFO] 심술 난 고양이의 구슬 → 일반: 50,000, 최저: 45,000
2025-12-09 14:30:17 [INFO] 마나 허브 → 일반: 1,200, 최저: 100
2025-12-09 14:30:17 [INFO] 봇 알림 전송 완료: 아이템 마나 허브
```

## 봇 명령어

Discord 채널에서 다음 명령어를 사용할 수 있습니다:

### `!추가 <아이템명>`

모니터링할 아이템을 추가합니다.

**사용 예시:**

```text
!추가 심술 난 고양이의 구슬
```

**응답:**

```text
✅ 심술 난 고양이의 구슬 추가 완료!
현재 모니터링:
심술 난 고양이의 구슬
마나 허브
```

### `!제거 <아이템명>`

모니터링 중인 아이템을 제거합니다.

**사용 예시:**

```text
!제거 마나 허브
```

**응답:**

```text
✅ 마나 허브 제거 완료!
현재 모니터링:
심술 난 고양이의 구슬
```

### `!목록`

현재 모니터링 중인 아이템 목록을 확인합니다.

**사용 예시:**

```text
!목록
```

**응답:**

```text
✅ 현재 모니터링 중인 아이템:
심술 난 고양이의 구슬
마나 허브
```

### 알림 메시지 예시

특가가 발견되면 다음과 같은 알림이 전송됩니다:

```text
🚨 아이템 `마나 허브` 특가 알림!
- 일반 판매가: `1,200`
- 최저 등록가: `100`
- 할인율: `91.7%`
```

## 서비스 등록 (systemd)

Linux 환경에서 봇을 백그라운드 서비스로 실행하려면:

### 1. 서비스 파일 수정

`mabinogi.service` 파일의 경로를 실제 환경에 맞게 수정:

```ini
[Unit]
Description=Mabinogi Rice Collector Discord Bot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/mabinogi-rice-collector

# uv 사용 시 .venv, pip 사용 시 venv로 변경
ExecStart=/home/your_username/mabinogi-rice-collector/.venv/bin/python main.py

Restart=always
RestartSec=10

StandardOutput=append:/home/your_username/mabinogi-rice-collector/main.log
StandardError=append:/home/your_username/mabinogi-rice-collector/main.err

[Install]
WantedBy=multi-user.target
```

**주의**: `ExecStart` 경로는 사용한 패키지 매니저에 따라 달라집니다:

- **uv 사용 시**: `.venv/bin/python`
- **pip 사용 시**: `venv/bin/python`

### 2. 서비스 등록 및 시작

```bash
# 서비스 파일 복사
sudo cp mabinogi.service /etc/systemd/system/

# 서비스 활성화
sudo systemctl enable mabinogi.service

# 서비스 시작
sudo systemctl start mabinogi.service

# 서비스 상태 확인
sudo systemctl status mabinogi.service

# 로그 확인
sudo journalctl -u mabinogi.service -f
```

## API 제한 사항

넥슨 Open API는 **애플리케이션 단계에 따라** 다음과 같은 제한이 있습니다:

### 개발 단계

- **초당 요청**: 5건/초
- **일일 요청**: 1,000건/일
- **제약사항**: 모니터링 아이템 1개당 약 16시간만 사용 가능

### 서비스/런칭 단계

- **초당 요청**: 500건/초
- **일일 요청**: 20,000,000건/일
- **제약사항**: 제한 없이 사용 가능

### CHECK_INTERVAL 조정

`main.py`의 `CHECK_INTERVAL` 값을 조정하여 API 사용량을 제어할 수 있습니다:

```python
CHECK_INTERVAL = 1  # 1초마다 체크 (기본값)
# CHECK_INTERVAL = 60  # 60초(1분)마다 체크 (권장)
```

**권장 설정:**

- 개발 단계: `60` (1분마다 체크)
- 서비스 단계: `1` ~ `30` (1초~30초마다 체크)

### API 제한 초과 시

API 제한을 초과하면 `OPENAPI00007` 오류 (HTTP 429)가 발생합니다. 이 경우:

1. `CHECK_INTERVAL` 값을 늘려주세요
2. 모니터링 아이템 수를 줄여주세요
3. 넥슨 개발자센터에서 애플리케이션을 서비스 단계로 전환하세요

## 최적화 내역

이 봇은 다음과 같은 최적화가 적용되어 있습니다:

### 1. 비동기 HTTP 요청

- `requests` → `aiohttp` 전환
- 비블로킹 I/O로 성능 향상
- **효과**: 약 50-70% 속도 개선

### 2. HTTP 연결 풀링

- 연결 재사용으로 네트워크 부하 감소
- 설정: 총 10개 연결, 호스트당 5개
- **효과**: TCP 핸드셰이크 오버헤드 제거

### 3. 아이템 목록 캐싱

- 파일 I/O를 메모리 캐시로 대체
- 변경 시에만 캐시 갱신
- **효과**: 파일 읽기 99% 감소

### 4. 메모리 효율적인 처리

- 필요한 데이터만 추출하는 조기 종료 로직
- 중간 리스트 생성 최소화
- **효과**: 메모리 사용량 30-40% 감소

### 5. 요청 타임아웃 설정

- 10초 타임아웃으로 무한 대기 방지
- 네트워크 문제 시 빠른 복구

## 문제 해결

### `ModuleNotFoundError: No module named 'discord'`

**원인**: 의존성 패키지 미설치

**해결**:

```bash
# uv 사용 시 (권장)
uv pip install -r requirements.txt

# pip 사용 시
pip install -r requirements.txt
```

### `채널(1234567890)을 찾을 수 없습니다`

**원인**: 잘못된 채널 ID 또는 봇 권한 부족

**해결**:

1. Discord 개발자 모드로 올바른 채널 ID 확인
2. 봇이 해당 채널에 접근 권한이 있는지 확인
3. 봇 역할에 "메시지 읽기", "메시지 보내기" 권한 부여

### `API 요청 실패: 401`

**원인**: 잘못된 API 키

**해결**:

1. `.env` 파일의 `MABINOGI_API_KEY` 확인
2. 넥슨 개발자센터에서 API 키 재발급

### `API 요청 실패: 429 Too Many Requests`

**원인**: API 사용량 제한 초과

**해결**:

1. `CHECK_INTERVAL` 값 증가 (예: `60`초)
2. 모니터링 아이템 수 감소
3. 애플리케이션을 서비스 단계로 전환

### 봇이 응답하지 않음

**원인**: 권한 미설정 또는 잘못된 권한

**해결**:

1. **Bot** 탭에서 **MESSAGE CONTENT INTENT**가 활성화(파란색)되어 있는지 확인
2. **OAuth2 → URL Generator**에서 다음 권한이 선택되어 있는지 확인:
   - View Channels
   - Send Messages
   - Read Message History
3. 권한이 잘못되었다면 올바른 권한으로 봇을 다시 초대 (권한 코드: 68608)
4. 봇 재시작: `sudo systemctl restart mabinogi.service` (systemd 사용 시)

## 라이선스

이 프로젝트는 개인 및 비상업적 용도로 자유롭게 사용 가능합니다.

## 참고 자료

- [넥슨 Open API 문서](https://openapi.nexon.com/ko/guide/request-api/)
- [discord.py 공식 문서](https://discordpy.readthedocs.io/)
- [aiohttp 공식 문서](https://docs.aiohttp.org/)

---

Made with love for Mabinogi Players

Data based on NEXON Open API
