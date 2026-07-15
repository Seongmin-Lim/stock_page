# AI_stockScope

무료·저(低)키 데이터로 동작하는 **로컬 웹 주식 분석 도구**. 브라우저에서 티커/종목명으로
검색해 차트·기술지표·재무·밸류에이션·스크리너(자연어 포함)·AI 추천·산업 사이클·매매(포지션·저널)·
관심/비교·포트폴리오·알림을 한 화면에서 본다. 한국(KOSPI/KOSDAQ) + 미국(NYSE/NASDAQ/S&P500) 지원.

> 숫자는 코드가, 서술만 AI가 — 모든 점수·지표·필터는 **결정적 규칙 기반**이고,
> Gemini는 (선택적으로) 사람이 읽을 서술 코멘트만 붙인다. 투자 권유가 아닌 참고용이다.

## 빠른 실행 (원클릭)

`start_stock.bat` **더블클릭** → 최초 1회 자동으로 가상환경 생성·의존성 설치 → 서버 기동 →
브라우저가 `http://127.0.0.1:8000` 으로 자동 진입. 8000번이 사용 중이면 8001~8010 중
빈 포트로 자동 전환하고 그 주소로 브라우저를 연다.

> 필요 조건: **Python 3.10+** (설치 시 "Add Python to PATH" 체크). 인터넷 연결(데이터 조회).

개발자용 실행:
```bash
pip install -r requirements.txt
python -m backend.server
```

## 탭 기능

| 탭 | 내용 |
|----|------|
| 개요 | 현재가·등락·시총·PER·PBR·EPS·배당·52주 고저 + 규칙 기반 종합 진단 |
| 차트 | 캔들+거래량, 이동평균·볼린저·EMA, MACD·RSI 서브패널, 기간/봉 선택, 차트 신호 읽기 |
| 재무·밸류 | (US) 손익·재무상태·현금흐름 + 멀티플, (KR) **DART 상세 재무제표** + 파생 비율, 2단계 DCF |
| 스크리너 | 규칙 필터(PER·PBR·ROE·시총·MA200·RSI·1년수익률·섹터) + **자연어 스크리닝**(문장 → 필터) |
| AI 추천 | 4카테고리(대형 우량 모멘텀 / 저평가 우량 / 독보적 강소 / 턴어라운드) + **전 시장 스캔** |
| 산업 사이클 | 테마별 4축(가격 모멘텀·이익·밸류·상대강도) 사이클 국면(회복·확장·둔화·침체) |
| 매매 | **포지션 계산기**(R 기반 사이징·ATR/가격/% 손절) + **매매 저널**(P&L·R·승률·기대값) |
| 관심·비교 | 워치리스트 저장, 정규화(시작=100) 수익률 비교, **관심종목 일일 브리핑** |
| 포트폴리오 | 보유 입력 → 평가액·비중·수익률·CAGR·MDD·Sharpe + equity curve, 전략 백테스트(체결 내역 포함) |
| 알림 | 가격·RSI·전일대비%·MA교차 조건 정의 후 점검 |

## 데이터 소스

| 용도 | KR | US |
|------|----|----|
| 검색/유니버스 | FinanceDataReader (KRX) | FinanceDataReader (NASDAQ/NYSE/AMEX/S&P500) |
| OHLCV | FinanceDataReader (일봉→주/월 리샘플) | FinanceDataReader |
| 시세/기초지표 | pykrx + FDR 스냅샷 | yfinance `.info` / `.fast_info` |
| 재무제표 | **DART 전자공시**(OpenDartReader, 연결재무제표) | yfinance 손익/재무/현금흐름 |
| 투자자 수급 | pykrx 외국인·기관 순매매 | — |

데이터는 **지연/EOD**(실시간 아님)이며 스크래핑 기반이라 간헐 실패가 있을 수 있다. 모든 호출은
`data/cache/`에 parquet+TTL로 캐시되어 두 번째부터 빠르다. 실패는 502/503 한국어 메시지로 처리된다.

## API 키 (`.env`, git 제외)

| 키 | 상태 | 역할 |
|----|------|------|
| `DART_API_KEY` | **활성** | KR 상세 재무제표(DART) — PER/PBR도 시총·순이익/자본에서 파생 |
| `GEMINI_API_KEY` | **활성** | (선택) 서술 코멘트 레이어 — 숫자엔 관여 안 함 |
| `KIWOOM_APP_KEY` / `KIWOOM_APP_SECRET` | 대기(미연동) | 실시간 시세·주문 연동 예정 |

키가 없어도 앱은 동작한다(무키 소스로 degrade). `GET /api/health`로 활성 상태 확인.

## AI 레이어 원칙 (숫자는 코드, 서술만 Gemini)

Gemini는 다음 7곳에서 **서술만** 담당하며, 점수·필터·수치는 항상 코드가 결정한다:
자연어 스크리닝(문장→필터), 종목 종합 진단 코멘트, 차트 신호 해석, 뉴스 요약·감성,
DART 공시 요약, 관심종목 일일 브리핑, (추천/사이클의) 서술 코멘트.

## 주요 엔드포인트

- 시장데이터: `/api/search` · `/api/quote` · `/api/ohlcv` · `/api/indicators`
- 진단·서술: `/api/analysis` · `/api/chartread` · `/api/news` · `/api/disclosures` · `/api/briefing`
- 재무·밸류: `/api/fundamentals` · `POST /api/dcf`
- 스크리너: `POST /api/screener` · `POST /api/nl-screen`
- 추천·스캔: `/api/recommend` · **`/api/turnaround-scan?market=KR|US&limit=24`**
- 사이클·수급: `/api/cycles` · `/api/flows` · **`/api/regime`**(지수 시황)
- 매매: `POST /api/position` · `/api/journal` (GET/POST/DELETE)
- 포트폴리오: `POST /api/portfolio` · `POST /api/backtest`(체결 내역 포함)
- 관심·알림: `/api/watchlist` · `/api/compare` · `/api/alerts`
- 상태: **`/api/health`**(dart/gemini/kiwoom 활성 여부)

## 한계

- 데이터는 **지연/EOD**, 스크래핑 기반이라 간헐 실패 가능(캐시로 완화).
- **전 시장 턴어라운드 스캔은 최초 1회 수 분** 소요(수백 종목 2단계 분석) — 이후 12시간 캐시.
- pykrx 기초지표(PER/PBR)는 자주 차단됨 → KR은 **DART 재무 + 시총에서 PER/PBR 파생**.
- 실시간 스트리밍·옵션체인·키움 주문 연동은 후속.

## 구조

```
backend/  server(FastAPI·라우팅·헬스·포트자동전환·캐시워밍업) · schema(pydantic 계약)
          sources · cache · store · universe(검색·섹터) · indicators · fundamentals(DCF)
          screener · nlscreen · recommend · scanner(전시장 스캔) · regime(시황)
          cycles · flows · portfolio(비교·백테스트) · trade(포지션) · journal · alerts
          analysis · chartread · news · disclosure · briefing · dart · llm · config · kiwoom
frontend/ index.html · style.css(Apple) · app.js · vendor/lightweight-charts
data/     캐시(parquet) + watchlist/portfolio/journal/alerts json (git 제외)
tests/    test_indicators · test_valuation · test_trade · test_journal · test_reversal · test_nlscreen
```

## 테스트

```bash
pytest tests/    # 지표·DCF·사이징·저널·리버설·자연어파서 순수함수 (네트워크 불필요)
```
