# AI_stockScope — 프로젝트 규칙

무료·저(低)키 데이터로 동작하는 로컬 웹 주식 분석 도구(FastAPI + vanilla JS). 브라우저로
접속 → 티커/종목명 검색 → 차트·기술지표·재무·밸류에이션·스크리너(+자연어)·AI 추천(4카테고리
+전 시장 스캔)·산업 사이클·매매(포지션·저널)·관심/비교(브리핑)·포트폴리오·알림. KR+US 지원.

## 핵심 원칙
- **숫자는 코드, 서술만 LLM.** 모든 점수·지표·필터는 결정적 규칙 기반. Gemini는 서술 코멘트만
  (자연어 스크리닝·진단·차트읽기·뉴스·공시·브리핑 등 7곳). 수치를 LLM이 만들게 하지 말 것.
- **저(低)키**: 무키 소스(FDR/yfinance/pykrx) 우선, DART·GEMINI 키는 있으면 기능 강화. 키가
  없어도 앱은 degrade 하며 동작해야 한다.
- **스크래핑 → 견고화 필수**: 모든 데이터 호출은 `cache.py`(parquet+TTL) 경유, 실패는
  graceful(502/503 한국어 메시지). 배치(추천/사이클/스캔)는 종목 실패 시 skip.
- `any`/`unknown` 금지. `from __future__ import annotations` + 타입힌트 유지.
- **pydantic `schema.py`가 sources↔API↔프론트 공통 계약.** 스키마 변경은 한 곳에서.
  프론트는 이 계약에 맞춰 코딩하므로 필드명·타입을 임의로 바꾸지 말 것.
- 시장 자동 판별: 6자리 숫자=KR, 그 외=US.
- 파일은 되도록 ~500줄 이하. Korean user-facing strings, English comments.
- 중복 지양: 공유 로직은 한 곳에(예: US 섹터맵은 `universe.US_SECTOR_KO` 단일 소스).

## 구조
```
backend/  server(라우팅·_guard·헬스·포트자동전환·캐시워밍업) · schema(계약) · sources(수집)
          cache · store(상태 json) · universe(검색·섹터) · indicators · fundamentals(DCF)
          screener · nlscreen · recommend · scanner(전시장 턴어라운드) · regime(지수 시황)
          cycles · flows · portfolio(비교·백테스트) · trade(포지션) · journal · alerts
          analysis · chartread · news · disclosure · briefing · dart · llm · config · kis
frontend/ index.html · style.css(Apple) · app.js · vendor/lightweight-charts
data/     캐시(parquet) + watchlist/portfolio/journal/alerts json (git 제외)
tests/    test_indicators · test_valuation · test_trade · test_journal · test_reversal · test_nlscreen
```

## 재사용 빌딩블록 (수정 전 시그니처 확인)
- `sources`: `get_ohlcv_df` · `kr_listing_snapshot` · `detect_market` · `_f`.
- `recommend`: `_metrics` · `_reversal_score` · `_turnaround_rationale/_sw` · `_fin_note` ·
  `TURNAROUND_WEIGHTS`. 턴어라운드 스캐너(`scanner`)는 이들을 그대로 재사용한다.
- `screener`: `_kr_fund_row` · `_us_fund_row` · `_us_snapshot`.
- `portfolio.backtest`: 벡터화 MA/RSI/buy-hold, `pos_lag`(1바 시프트) → 체결 내역 파생.
- `universe.sector_of` / `US_SECTOR_KO`(단일 US 섹터맵) / `_kr_sectors`.
- `config.has_dart/has_gemini/has_kis`.

## 실행
- 사용자: `start_stock.bat` 더블클릭 → (최초) 자동 설치 → 서버 → 브라우저 자동 오픈.
  8000 사용 중이면 `_free_port`가 8001~8010 중 빈 포트로 전환.
- 개발: `./.venv/Scripts/python.exe -m backend.server` (또는 uvicorn 직접 기동).
- 헬스: `GET /api/health` → `{ok, features:{dart,gemini,kis}}`.

## 검증
- `python -m py_compile backend/*.py` — 문법 확인.
- `pytest tests/ -q` — 순수함수(지표·DCF·사이징·저널·리버설·자연어파서)는 네트워크 없이 통과해야 함.
- 스모크: uvicorn을 8061~8069 임시 포트로 기동해 `/api/health`·`/api/regime` 등 확인,
  전 시장 스캔은 pool/finalist 캡을 낮춰 소량으로만 검증(전체 KR 350종목 스캔 금지).
- 콘솔 한글은 cp949 mojibake가 날 수 있음 — 검증은 JSON을 utf-8 파일로 쓰고 ASCII만 출력.

## 보고
사용자 보고는 한국어, 코드·주석·커밋은 영어 위주. 이 repo는 자동 commit/push 하지 않음
(자동 push는 Claude_database 한정). `.env` 값은 수정 금지(읽기만).
