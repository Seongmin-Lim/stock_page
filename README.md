# 📊 AI 기반 주식 분석 대시보드

VIX, 10년 금리, S&P Forward P/E, 공포탐욕 지수, PER, PBR 등을 활용한 종합 주식 분석 도구입니다.  
**Streamlit 웹 대시보드**와 **CLI 인터페이스**를 모두 지원합니다.

## 🌐 라이브 데모

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## 🚀 주요 기능

### 시장 분석
- **VIX (변동성 지수)**: 시장 공포/안정 수준 측정
- **10년 국채 금리**: 금리 환경 및 채권 시장 동향
- **S&P 500 Forward P/E**: 시장 밸류에이션 수준
- **공포탐욕 지수**: CNN Fear & Greed Index 및 자체 계산
- **경기 사이클 분석**: 회복기/확장기/과열기/수축기/침체기 자동 판별

### 개별 주식 분석
- **밸류에이션**: PER, PBR, PEG, PSR 등
- **재무 지표**: 이익률, 성장률, ROE 등
- **기술적 분석**: RSI, MACD, 볼린저밴드, 이동평균 등
- **섹터 비교**: 동종 업계 평균과 비교

### AI 분석 (5개 제공자 지원)
- **Grok (xAI)**: 빠르고 비용 효율적, 한국어 우수
- **Gemini (Google)**: 무료 티어 제공, 긴 컨텍스트
- **OpenAI GPT**: GPT-4o 등 프리미엄 모델
- **Anthropic Claude**: 복잡한 분석에 적합
- **GitHub Models**: 10+ 모델 선택 (Llama, Phi, Mistral 등)

### 포트폴리오 기능
- 유명 투자자 포트폴리오 비교 (워렌 버핏, 레이 달리오 등)
- 리밸런싱 계산기
- 사용자 포트폴리오 관리

## 📁 프로젝트 구조

```
stock_page/
├── app.py                    # 🌐 Streamlit 웹 대시보드 (메인)
├── main.py                   # CLI 메인 실행 파일
├── interactive.py            # CLI 대화형 인터페이스
├── requirements.txt          # 의존성
├── .env.example              # 환경변수 예시
│
├── config/
│   ├── settings.py           # 설정 및 API 키
│   └── portfolio_data.py     # 유명 포트폴리오 데이터
│
├── data_collectors/
│   ├── market_data.py        # VIX, 금리, S&P 500 데이터
│   ├── fear_greed.py         # 공포탐욕 지수
│   ├── stock_fundamentals.py # PER, PBR 등 기본적 분석
│   ├── economic_cycle.py     # 경기 사이클 분석
│   ├── economic_indicators.py# 경제 지표
│   └── news_collector.py     # 뉴스 수집 및 감성 분석
│
├── analyzers/
│   ├── ai_analyzer.py        # AI 기반 분석 (멀티 프로바이더)
│   ├── technical_analyzer.py # 기술적 분석
│   └── portfolio_analyzer.py # 포트폴리오 분석
│
├── ai_providers/
│   ├── github_models.py      # GitHub Models API
│   ├── ai_debate.py          # AI 토론 기능
│   └── team_debate.py        # 팀 토론 기능
│
├── database/
│   └── db_manager.py         # PostgreSQL DB 관리
│
├── utils/
│   ├── helpers.py            # 유틸리티 함수
│   ├── visualizer.py         # 차트 생성
│   ├── rebalance_calculator.py # 리밸런싱 계산
│   └── report_generator.py   # 리포트 생성
│
├── reports/                  # 분석 리포트 저장
│   ├── daily/
│   ├── market/
│   ├── stocks/
│   └── portfolio/
│
└── test_setup.py             # 설정 테스트
```

## 🛠️ 설치 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env.example`을 `.env`로 복사하고 API 키를 입력하세요:

```bash
cp .env.example .env
```

```env
# .env 파일
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here
XAI_API_KEY=your_grok_api_key_here
GITHUB_TOKEN=your_github_pat_here
```

## 📖 사용 방법

### 🌐 웹 대시보드 (Streamlit) - 권장
```bash
streamlit run app.py
```

### CLI 대화형 모드
```bash
python interactive.py
```

### CLI 기본 실행
```bash
python main.py
```

### 코드에서 직접 사용
```python
from main import StockAnalyzer

# 분석기 초기화 (AI 제공자 선택: grok, gemini, openai, anthropic, github)
analyzer = StockAnalyzer(ai_provider="grok")

# 경기 사이클 확인
cycle = analyzer.get_economic_cycle()
print(cycle)

# 시장 현황 확인
analyzer.print_market_summary()

# 개별 주식 분석
analyzer.print_stock_summary("AAPL")

# AI 시장 분석
analysis = analyzer.get_ai_market_analysis()
print(analysis)

# AI 주식 분석
stock_analysis = analyzer.get_ai_stock_analysis("MSFT")
print(stock_analysis)

# 포트폴리오 추천
recommendation = analyzer.get_portfolio_recommendation(
    tickers=["AAPL", "MSFT", "GOOGL"],
    risk_tolerance="moderate"
)
print(recommendation)
```

## 📊 분석 지표 설명

### VIX (변동성 지수)
| 수준 | 값 | 의미 |
|------|-----|------|
| 매우 낮음 | < 12 | 극도의 안정/자만 |
| 낮음 | 12-17 | 낙관적 시장 |
| 보통 | 17-22 | 정상 범위 |
| 높음 | 22-30 | 불안정 |
| 매우 높음 | > 30 | 공포 (역발상 기회) |

### 공포탐욕 지수
| 수준 | 값 | 역발상 전략 |
|------|-----|------|
| 극도의 공포 | 0-25 | 매수 기회 |
| 공포 | 25-45 | 매수 고려 |
| 중립 | 45-55 | 관망 |
| 탐욕 | 55-75 | 매도 고려 |
| 극도의 탐욕 | 75-100 | 매도 기회 |

### 경기 사이클
| 단계 | PER 조정 | 전략 |
|------|----------|------|
| 회복기 | ×0.9 | 성장주 비중 확대 |
| 확장기 | ×1.0 | 균형 포트폴리오 |
| 과열기 | ×1.1 | 방어주/현금 확대 |
| 수축기 | ×0.85 | 채권/금 비중 확대 |
| 침체기 | ×0.8 | 저점 매수 준비 |

### PER (주가수익비율)
- **< 15**: 저평가 가능
- **15-20**: 적정 수준
- **> 25**: 고평가 (성장주 제외)

### PBR (주가순자산비율)
- **< 1**: 청산가치 이하 (저평가)
- **1-3**: 합리적 수준
- **> 4**: 높은 프리미엄

---

## ☁️ Streamlit Cloud 배포 방법

### 1. GitHub 저장소 준비
이미 GitHub에 푸시되어 있다면 바로 다음 단계로 이동하세요.

### 2. Streamlit Cloud 접속
1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 계정으로 로그인

### 3. 새 앱 배포
1. **"New app"** 클릭
2. 설정 입력:
   - **Repository**: `tjdal/stock_page` (본인 GitHub username/repo)
   - **Branch**: `main`
   - **Main file path**: `app.py` ← ⭐ 이것만 입력하면 됨!

### 4. Secrets 설정 (중요!)
배포 전 **"Advanced settings"** 클릭 후 Secrets에 API 키 입력:

```toml
# secrets.toml 형식
OPENAI_API_KEY = "sk-..."
ANTHROPIC_API_KEY = "sk-ant-..."
GOOGLE_API_KEY = "AIza..."
XAI_API_KEY = "xai-..."
GITHUB_TOKEN = "ghp_..."

# 앱 접근 비밀번호 (선택)
APP_PASSWORD = "your_password"

# PostgreSQL (선택)
DATABASE_URL = "postgresql://..."
```

### 5. 배포
**"Deploy!"** 버튼 클릭하면 자동 빌드 및 배포됩니다.

### 📌 Main File Path 요약
| 질문 | 답변 |
|------|------|
| Main file path에 뭘 입력? | **`app.py`** |
| 전체 경로 필요? | ❌ 파일명만 입력 |
| 왜 app.py? | Streamlit 대시보드가 여기에 있음 |

---

## ⚠️ 주의사항

1. **투자 조언이 아닙니다**: 이 프로그램은 정보 제공 목적이며, 투자 결정은 본인 책임입니다.
2. **데이터 정확성**: 실시간 데이터는 지연될 수 있으며, 일부 지표는 추정치입니다.
3. **API 비용**: AI 분석 기능은 API 호출 비용이 발생할 수 있습니다 (Gemini 무료 티어 제외).

## 🧪 테스트

```bash
# 설정 및 데이터 수집 테스트
python test_setup.py

# 새 기능 테스트
python test_new_features.py
```

## 📝 라이센스

MIT License

## 🤝 기여

버그 리포트나 기능 제안은 Issue를 통해 제출해주세요.
