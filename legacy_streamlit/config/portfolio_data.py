"""
추천 포트폴리오 및 섹터별 대표 주식/ETF 데이터
"""

# ============================================================
# 투자 스타일별 추천 포트폴리오
# ============================================================

RECOMMENDED_PORTFOLIOS = {
    "growth": {
        "name": "🚀 성장형 포트폴리오",
        "description": "고성장 기업 중심, 장기 자본이득 추구. 변동성 높지만 높은 수익 잠재력",
        "risk_level": "높음",
        "suitable_for": "장기 투자자, 높은 변동성 감내 가능한 투자자",
        "time_horizon": "5년 이상",
        "allocation": {
            "QQQ": {"weight": 35, "name": "Invesco QQQ Trust", "type": "ETF", "description": "나스닥 100 추종"},
            "VUG": {"weight": 20, "name": "Vanguard Growth ETF", "type": "ETF", "description": "미국 대형 성장주"},
            "ARKK": {"weight": 10, "name": "ARK Innovation ETF", "type": "ETF", "description": "혁신 기술주"},
            "SMH": {"weight": 15, "name": "VanEck Semiconductor ETF", "type": "ETF", "description": "반도체"},
            "VGT": {"weight": 15, "name": "Vanguard Info Tech ETF", "type": "ETF", "description": "IT 섹터"},
            "CASH": {"weight": 5, "name": "현금", "type": "현금", "description": "기회 대비용"}
        },
        "key_stocks": ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AMD"],
        "expected_return": "12-18%",
        "expected_volatility": "20-30%"
    },
    
    "dividend": {
        "name": "💰 배당형 포트폴리오",
        "description": "안정적인 배당 수익 추구, 배당 성장 기업 중심. 인컴 투자자에게 적합",
        "risk_level": "중간",
        "suitable_for": "은퇴자, 정기 수입 필요한 투자자",
        "time_horizon": "3년 이상",
        "allocation": {
            "VYM": {"weight": 25, "name": "Vanguard High Dividend Yield", "type": "ETF", "description": "고배당 대형주"},
            "SCHD": {"weight": 25, "name": "Schwab US Dividend Equity", "type": "ETF", "description": "배당 성장주"},
            "VIG": {"weight": 20, "name": "Vanguard Dividend Appreciation", "type": "ETF", "description": "배당 증가 기업"},
            "JEPI": {"weight": 15, "name": "JPMorgan Equity Premium Income", "type": "ETF", "description": "월배당 + 프리미엄"},
            "O": {"weight": 10, "name": "Realty Income Corp", "type": "REIT", "description": "월배당 리츠"},
            "CASH": {"weight": 5, "name": "현금", "type": "현금", "description": "재투자용"}
        },
        "key_stocks": ["JNJ", "PG", "KO", "PEP", "MCD", "VZ", "T", "XOM", "CVX"],
        "expected_return": "6-10%",
        "expected_volatility": "12-18%",
        "expected_yield": "3-5%"
    },
    
    "balanced": {
        "name": "⚖️ 균형형 포트폴리오",
        "description": "성장과 안정성의 균형, 중간 수준의 위험과 수익 추구",
        "risk_level": "중간",
        "suitable_for": "대부분의 투자자, 균형 잡힌 접근 선호",
        "time_horizon": "3-5년",
        "allocation": {
            "VTI": {"weight": 40, "name": "Vanguard Total Stock Market", "type": "ETF", "description": "미국 전체 시장"},
            "VXUS": {"weight": 15, "name": "Vanguard Total International", "type": "ETF", "description": "해외 주식"},
            "BND": {"weight": 25, "name": "Vanguard Total Bond Market", "type": "ETF", "description": "미국 채권"},
            "VNQ": {"weight": 10, "name": "Vanguard Real Estate", "type": "ETF", "description": "부동산"},
            "GLD": {"weight": 5, "name": "SPDR Gold Shares", "type": "ETF", "description": "금"},
            "CASH": {"weight": 5, "name": "현금", "type": "현금", "description": "유동성"}
        },
        "key_stocks": ["AAPL", "MSFT", "JPM", "JNJ", "PG", "BRK.B"],
        "expected_return": "7-10%",
        "expected_volatility": "10-15%"
    },
    
    "aggressive": {
        "name": "🔥 공격형 포트폴리오",
        "description": "최대 수익 추구, 높은 위험 감수. 레버리지 ETF 포함",
        "risk_level": "매우 높음",
        "suitable_for": "젊은 투자자, 높은 위험 감내 가능, 단기 트레이딩",
        "time_horizon": "단기~중기",
        "allocation": {
            "TQQQ": {"weight": 20, "name": "ProShares UltraPro QQQ", "type": "ETF", "description": "나스닥 3배 레버리지"},
            "SOXL": {"weight": 15, "name": "Direxion Daily Semiconductor 3X", "type": "ETF", "description": "반도체 3배"},
            "QQQ": {"weight": 25, "name": "Invesco QQQ Trust", "type": "ETF", "description": "나스닥 100"},
            "ARKK": {"weight": 15, "name": "ARK Innovation ETF", "type": "ETF", "description": "혁신 기술"},
            "SOXX": {"weight": 15, "name": "iShares Semiconductor ETF", "type": "ETF", "description": "반도체"},
            "CASH": {"weight": 10, "name": "현금", "type": "현금", "description": "리밸런싱용"}
        },
        "key_stocks": ["NVDA", "AMD", "TSLA", "PLTR", "COIN", "MSTR"],
        "expected_return": "20-40%+",
        "expected_volatility": "40-60%+",
        "warning": "⚠️ 레버리지 ETF는 장기 보유 시 손실 위험이 매우 높습니다!"
    },
    
    "conservative": {
        "name": "🛡️ 안정형 포트폴리오",
        "description": "원금 보존 최우선, 낮은 변동성, 꾸준한 수익",
        "risk_level": "낮음",
        "suitable_for": "은퇴 근접자, 원금 보존 최우선",
        "time_horizon": "1-3년",
        "allocation": {
            "BND": {"weight": 35, "name": "Vanguard Total Bond Market", "type": "ETF", "description": "채권"},
            "VCSH": {"weight": 20, "name": "Vanguard Short-Term Corporate", "type": "ETF", "description": "단기 회사채"},
            "VTI": {"weight": 20, "name": "Vanguard Total Stock Market", "type": "ETF", "description": "주식"},
            "TIP": {"weight": 10, "name": "iShares TIPS Bond ETF", "type": "ETF", "description": "물가연동채"},
            "GLD": {"weight": 5, "name": "SPDR Gold Shares", "type": "ETF", "description": "금"},
            "CASH": {"weight": 10, "name": "현금", "type": "현금", "description": "안전자산"}
        },
        "key_stocks": ["JNJ", "PG", "KO", "WMT", "UNH"],
        "expected_return": "4-6%",
        "expected_volatility": "5-10%"
    },
    
    "esg": {
        "name": "🌱 ESG/친환경 포트폴리오",
        "description": "환경, 사회, 지배구조 우수 기업 투자. 지속가능한 투자",
        "risk_level": "중간",
        "suitable_for": "가치 투자자, 사회적 책임 투자 관심",
        "time_horizon": "5년 이상",
        "allocation": {
            "ESGU": {"weight": 30, "name": "iShares ESG Aware MSCI USA", "type": "ETF", "description": "ESG 미국주"},
            "ICLN": {"weight": 20, "name": "iShares Global Clean Energy", "type": "ETF", "description": "클린에너지"},
            "QCLN": {"weight": 15, "name": "First Trust NASDAQ Clean Edge", "type": "ETF", "description": "청정기술"},
            "TAN": {"weight": 10, "name": "Invesco Solar ETF", "type": "ETF", "description": "태양광"},
            "LIT": {"weight": 10, "name": "Global X Lithium & Battery Tech", "type": "ETF", "description": "리튬/배터리"},
            "ESGV": {"weight": 10, "name": "Vanguard ESG US Stock", "type": "ETF", "description": "ESG 스크리닝"},
            "CASH": {"weight": 5, "name": "현금", "type": "현금", "description": "유동성"}
        },
        "key_stocks": ["TSLA", "ENPH", "SEDG", "NEE", "FSLR", "RIVN"],
        "expected_return": "8-14%",
        "expected_volatility": "18-25%"
    },
    
    "tech_focused": {
        "name": "💻 테크 집중 포트폴리오",
        "description": "기술주 집중 투자, AI/클라우드/반도체 테마",
        "risk_level": "높음",
        "suitable_for": "기술 산업 확신 있는 투자자",
        "time_horizon": "3-5년",
        "allocation": {
            "QQQ": {"weight": 30, "name": "Invesco QQQ Trust", "type": "ETF", "description": "나스닥 100"},
            "SMH": {"weight": 20, "name": "VanEck Semiconductor ETF", "type": "ETF", "description": "반도체"},
            "SKYY": {"weight": 15, "name": "First Trust Cloud Computing", "type": "ETF", "description": "클라우드"},
            "BOTZ": {"weight": 15, "name": "Global X Robotics & AI", "type": "ETF", "description": "AI/로봇"},
            "CIBR": {"weight": 10, "name": "First Trust NASDAQ Cybersecurity", "type": "ETF", "description": "사이버보안"},
            "CASH": {"weight": 10, "name": "현금", "type": "현금", "description": "기회 대비"}
        },
        "key_stocks": ["NVDA", "AAPL", "MSFT", "GOOGL", "AMD", "AVGO", "CRM", "SNOW"],
        "expected_return": "12-20%",
        "expected_volatility": "22-32%"
    }
}

# ============================================================
# 섹터별 대표 주식 및 ETF
# ============================================================

SECTOR_REPRESENTATIVES = {
    "기술": {
        "name": "Technology",
        "description": "소프트웨어, 하드웨어, 반도체, IT 서비스",
        "stocks": [
            {"ticker": "AAPL", "name": "Apple Inc.", "description": "세계 최대 기술기업, 아이폰/맥/서비스"},
            {"ticker": "MSFT", "name": "Microsoft Corp.", "description": "클라우드(Azure), 오피스, AI"},
            {"ticker": "GOOGL", "name": "Alphabet Inc.", "description": "검색, 유튜브, 클라우드, AI"},
            {"ticker": "NVDA", "name": "NVIDIA Corp.", "description": "AI/GPU 리더, 데이터센터"},
            {"ticker": "META", "name": "Meta Platforms", "description": "소셜미디어, 메타버스"},
        ],
        "etfs": [
            {"ticker": "VGT", "name": "Vanguard Information Technology ETF", "expense_ratio": 0.10, "aum": "65B", "description": "IT 섹터 전체"},
            {"ticker": "XLK", "name": "Technology Select Sector SPDR", "expense_ratio": 0.09, "aum": "45B", "description": "S&P 500 IT"},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "expense_ratio": 0.20, "aum": "200B", "description": "나스닥 100"},
            {"ticker": "SMH", "name": "VanEck Semiconductor ETF", "expense_ratio": 0.35, "aum": "15B", "description": "반도체 집중"},
        ]
    },
    
    "헬스케어": {
        "name": "Healthcare",
        "description": "제약, 바이오테크, 의료기기, 헬스케어 서비스",
        "stocks": [
            {"ticker": "UNH", "name": "UnitedHealth Group", "description": "미국 최대 건강보험"},
            {"ticker": "JNJ", "name": "Johnson & Johnson", "description": "다각화된 헬스케어"},
            {"ticker": "LLY", "name": "Eli Lilly", "description": "비만/당뇨 치료제 리더"},
            {"ticker": "PFE", "name": "Pfizer Inc.", "description": "대형 제약사"},
            {"ticker": "ABBV", "name": "AbbVie Inc.", "description": "면역학/종양학"},
        ],
        "etfs": [
            {"ticker": "VHT", "name": "Vanguard Health Care ETF", "expense_ratio": 0.10, "aum": "18B", "description": "헬스케어 전체"},
            {"ticker": "XLV", "name": "Health Care Select Sector SPDR", "expense_ratio": 0.09, "aum": "38B", "description": "S&P 500 헬스케어"},
            {"ticker": "IBB", "name": "iShares Biotechnology ETF", "expense_ratio": 0.44, "aum": "7B", "description": "바이오테크"},
            {"ticker": "XBI", "name": "SPDR S&P Biotech ETF", "expense_ratio": 0.35, "aum": "6B", "description": "소형 바이오테크"},
        ]
    },
    
    "금융": {
        "name": "Financials",
        "description": "은행, 보험, 자산운용, 핀테크",
        "stocks": [
            {"ticker": "JPM", "name": "JPMorgan Chase", "description": "미국 최대 은행"},
            {"ticker": "BAC", "name": "Bank of America", "description": "대형 상업은행"},
            {"ticker": "V", "name": "Visa Inc.", "description": "글로벌 결제 네트워크"},
            {"ticker": "MA", "name": "Mastercard Inc.", "description": "결제 기술"},
            {"ticker": "BRK.B", "name": "Berkshire Hathaway", "description": "워렌 버핏 지주회사"},
        ],
        "etfs": [
            {"ticker": "VFH", "name": "Vanguard Financials ETF", "expense_ratio": 0.10, "aum": "10B", "description": "금융 섹터 전체"},
            {"ticker": "XLF", "name": "Financial Select Sector SPDR", "expense_ratio": 0.09, "aum": "35B", "description": "S&P 500 금융"},
            {"ticker": "KBE", "name": "SPDR S&P Bank ETF", "expense_ratio": 0.35, "aum": "2B", "description": "은행 집중"},
            {"ticker": "KRE", "name": "SPDR S&P Regional Banking ETF", "expense_ratio": 0.35, "aum": "3B", "description": "지방은행"},
        ]
    },
    
    "에너지": {
        "name": "Energy",
        "description": "석유, 천연가스, 신재생에너지",
        "stocks": [
            {"ticker": "XOM", "name": "Exxon Mobil", "description": "세계 최대 에너지 기업"},
            {"ticker": "CVX", "name": "Chevron Corp.", "description": "통합 에너지 기업"},
            {"ticker": "COP", "name": "ConocoPhillips", "description": "석유/가스 탐사"},
            {"ticker": "SLB", "name": "Schlumberger", "description": "유전 서비스"},
            {"ticker": "NEE", "name": "NextEra Energy", "description": "신재생에너지 리더"},
        ],
        "etfs": [
            {"ticker": "VDE", "name": "Vanguard Energy ETF", "expense_ratio": 0.10, "aum": "8B", "description": "에너지 전체"},
            {"ticker": "XLE", "name": "Energy Select Sector SPDR", "expense_ratio": 0.09, "aum": "35B", "description": "S&P 500 에너지"},
            {"ticker": "ICLN", "name": "iShares Global Clean Energy", "expense_ratio": 0.40, "aum": "3B", "description": "클린에너지"},
            {"ticker": "TAN", "name": "Invesco Solar ETF", "expense_ratio": 0.67, "aum": "1.5B", "description": "태양광"},
        ]
    },
    
    "소비재": {
        "name": "Consumer",
        "description": "필수소비재, 임의소비재, 리테일",
        "stocks": [
            {"ticker": "AMZN", "name": "Amazon.com", "description": "이커머스/클라우드"},
            {"ticker": "WMT", "name": "Walmart Inc.", "description": "세계 최대 소매업"},
            {"ticker": "COST", "name": "Costco Wholesale", "description": "회원제 창고형 매장"},
            {"ticker": "PG", "name": "Procter & Gamble", "description": "생활용품"},
            {"ticker": "KO", "name": "Coca-Cola", "description": "음료"},
        ],
        "etfs": [
            {"ticker": "VDC", "name": "Vanguard Consumer Staples ETF", "expense_ratio": 0.10, "aum": "7B", "description": "필수소비재"},
            {"ticker": "XLP", "name": "Consumer Staples Select SPDR", "expense_ratio": 0.09, "aum": "16B", "description": "S&P 필수소비재"},
            {"ticker": "VCR", "name": "Vanguard Consumer Discretionary", "expense_ratio": 0.10, "aum": "5B", "description": "임의소비재"},
            {"ticker": "XLY", "name": "Consumer Discretionary Select SPDR", "expense_ratio": 0.09, "aum": "18B", "description": "S&P 임의소비재"},
        ]
    },
    
    "산업재": {
        "name": "Industrials",
        "description": "항공우주, 방위산업, 건설, 운송",
        "stocks": [
            {"ticker": "CAT", "name": "Caterpillar Inc.", "description": "건설/광업 장비"},
            {"ticker": "BA", "name": "Boeing Co.", "description": "항공우주"},
            {"ticker": "UNP", "name": "Union Pacific", "description": "철도 운송"},
            {"ticker": "HON", "name": "Honeywell International", "description": "다각화 산업"},
            {"ticker": "LMT", "name": "Lockheed Martin", "description": "방위산업"},
        ],
        "etfs": [
            {"ticker": "VIS", "name": "Vanguard Industrials ETF", "expense_ratio": 0.10, "aum": "5B", "description": "산업재 전체"},
            {"ticker": "XLI", "name": "Industrial Select Sector SPDR", "expense_ratio": 0.09, "aum": "17B", "description": "S&P 500 산업재"},
            {"ticker": "ITA", "name": "iShares US Aerospace & Defense", "expense_ratio": 0.40, "aum": "5B", "description": "방위산업"},
            {"ticker": "IYT", "name": "iShares Transportation Average", "expense_ratio": 0.40, "aum": "1B", "description": "운송"},
        ]
    },
    
    "부동산": {
        "name": "Real Estate",
        "description": "REITs, 상업용/주거용 부동산",
        "stocks": [
            {"ticker": "PLD", "name": "Prologis Inc.", "description": "물류 부동산 리츠"},
            {"ticker": "AMT", "name": "American Tower", "description": "통신 인프라 리츠"},
            {"ticker": "EQIX", "name": "Equinix Inc.", "description": "데이터센터 리츠"},
            {"ticker": "O", "name": "Realty Income", "description": "월배당 리테일 리츠"},
            {"ticker": "SPG", "name": "Simon Property Group", "description": "쇼핑몰 리츠"},
        ],
        "etfs": [
            {"ticker": "VNQ", "name": "Vanguard Real Estate ETF", "expense_ratio": 0.12, "aum": "35B", "description": "미국 리츠 전체"},
            {"ticker": "XLRE", "name": "Real Estate Select Sector SPDR", "expense_ratio": 0.09, "aum": "5B", "description": "S&P 500 리츠"},
            {"ticker": "IYR", "name": "iShares US Real Estate ETF", "expense_ratio": 0.39, "aum": "4B", "description": "미국 부동산"},
            {"ticker": "VNQI", "name": "Vanguard Global ex-US Real Estate", "expense_ratio": 0.12, "aum": "5B", "description": "해외 부동산"},
        ]
    },
    
    "유틸리티": {
        "name": "Utilities",
        "description": "전력, 가스, 수도 공급",
        "stocks": [
            {"ticker": "NEE", "name": "NextEra Energy", "description": "신재생에너지 리더"},
            {"ticker": "DUK", "name": "Duke Energy", "description": "전력 공급"},
            {"ticker": "SO", "name": "Southern Company", "description": "남부 전력"},
            {"ticker": "D", "name": "Dominion Energy", "description": "전력/가스"},
            {"ticker": "AEP", "name": "American Electric Power", "description": "전력 공급"},
        ],
        "etfs": [
            {"ticker": "VPU", "name": "Vanguard Utilities ETF", "expense_ratio": 0.10, "aum": "5B", "description": "유틸리티 전체"},
            {"ticker": "XLU", "name": "Utilities Select Sector SPDR", "expense_ratio": 0.09, "aum": "14B", "description": "S&P 500 유틸리티"},
            {"ticker": "IDU", "name": "iShares US Utilities ETF", "expense_ratio": 0.39, "aum": "1B", "description": "미국 유틸리티"},
        ]
    },
    
    "원자재": {
        "name": "Materials",
        "description": "금속, 화학, 광업, 건축자재",
        "stocks": [
            {"ticker": "LIN", "name": "Linde plc", "description": "산업 가스"},
            {"ticker": "APD", "name": "Air Products", "description": "산업 가스"},
            {"ticker": "SHW", "name": "Sherwin-Williams", "description": "페인트/도료"},
            {"ticker": "FCX", "name": "Freeport-McMoRan", "description": "구리/금 채굴"},
            {"ticker": "NEM", "name": "Newmont Corp.", "description": "금 채굴"},
        ],
        "etfs": [
            {"ticker": "VAW", "name": "Vanguard Materials ETF", "expense_ratio": 0.10, "aum": "3B", "description": "원자재 전체"},
            {"ticker": "XLB", "name": "Materials Select Sector SPDR", "expense_ratio": 0.09, "aum": "5B", "description": "S&P 500 원자재"},
            {"ticker": "GLD", "name": "SPDR Gold Shares", "expense_ratio": 0.40, "aum": "55B", "description": "금"},
            {"ticker": "SLV", "name": "iShares Silver Trust", "expense_ratio": 0.50, "aum": "10B", "description": "은"},
        ]
    },
    
    "통신": {
        "name": "Communication Services",
        "description": "통신, 미디어, 엔터테인먼트",
        "stocks": [
            {"ticker": "GOOGL", "name": "Alphabet Inc.", "description": "검색/유튜브"},
            {"ticker": "META", "name": "Meta Platforms", "description": "소셜미디어"},
            {"ticker": "DIS", "name": "Walt Disney", "description": "엔터테인먼트"},
            {"ticker": "NFLX", "name": "Netflix Inc.", "description": "스트리밍"},
            {"ticker": "VZ", "name": "Verizon Communications", "description": "통신"},
        ],
        "etfs": [
            {"ticker": "VOX", "name": "Vanguard Communication Services", "expense_ratio": 0.10, "aum": "3B", "description": "통신 전체"},
            {"ticker": "XLC", "name": "Communication Services Select SPDR", "expense_ratio": 0.09, "aum": "12B", "description": "S&P 통신"},
            {"ticker": "FCOM", "name": "Fidelity MSCI Communication Services", "expense_ratio": 0.08, "aum": "1B", "description": "통신 서비스"},
        ]
    }
}


# ============================================================
# 대표 주식 리스트 (시장 분석용)
# ============================================================

REPRESENTATIVE_STOCKS = {
    "mega_cap": {
        "name": "메가캡 (시총 2000억$ 이상)",
        "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B"]
    },
    "blue_chip": {
        "name": "우량주 (블루칩)",
        "tickers": ["JPM", "JNJ", "V", "PG", "UNH", "HD", "MA", "DIS"]
    },
    "growth_leaders": {
        "name": "성장주 리더",
        "tickers": ["NVDA", "AMD", "CRM", "NOW", "SNOW", "PLTR", "NET", "DDOG"]
    },
    "dividend_aristocrats": {
        "name": "배당 귀족주",
        "tickers": ["JNJ", "PG", "KO", "PEP", "MMM", "ABT", "MCD", "WMT"]
    },
    "value_stocks": {
        "name": "가치주",
        "tickers": ["BRK.B", "JPM", "BAC", "CVX", "XOM", "VZ", "INTC", "IBM"]
    }
}


# ============================================================
# 경제 사이클별 추천 조정
# ============================================================

CYCLE_PORTFOLIO_ADJUSTMENTS = {
    "회복기": {
        "preferred_style": "growth",
        "sector_overweight": ["기술", "소비재", "산업재"],
        "sector_underweight": ["유틸리티", "헬스케어"],
        "allocation_shift": {"주식": +10, "채권": -5, "현금": -5}
    },
    "확장기": {
        "preferred_style": "growth",
        "sector_overweight": ["기술", "금융", "산업재"],
        "sector_underweight": ["유틸리티", "필수소비재"],
        "allocation_shift": {"주식": +5, "채권": -5, "현금": 0}
    },
    "과열기": {
        "preferred_style": "balanced",
        "sector_overweight": ["에너지", "원자재", "금융"],
        "sector_underweight": ["기술", "부동산"],
        "allocation_shift": {"주식": -5, "채권": 0, "현금": +5}
    },
    "수축기": {
        "preferred_style": "conservative",
        "sector_overweight": ["헬스케어", "유틸리티", "필수소비재"],
        "sector_underweight": ["기술", "소비재", "금융"],
        "allocation_shift": {"주식": -10, "채권": +5, "현금": +5}
    },
    "침체기": {
        "preferred_style": "conservative",
        "sector_overweight": ["헬스케어", "유틸리티", "필수소비재"],
        "sector_underweight": ["기술", "금융", "에너지"],
        "allocation_shift": {"주식": -15, "채권": +10, "현금": +5}
    }
}


# ============================================================
# 자산 클래스별 추천 (마우스 호버용)
# ============================================================

ASSET_CLASS_RECOMMENDATIONS = {
    "주식": {
        "icon": "📈",
        "description": "성장성 높은 기업에 투자",
        "etfs": [
            {"ticker": "VTI", "name": "Vanguard Total Stock Market", "expense": 0.03},
            {"ticker": "QQQ", "name": "Invesco QQQ (나스닥100)", "expense": 0.20},
            {"ticker": "SPY", "name": "SPDR S&P 500", "expense": 0.09},
        ],
        "sectors": {
            "회복기": ["기술", "소비재", "산업재"],
            "확장기": ["기술", "금융", "산업재"],
            "과열기": ["에너지", "원자재", "금융"],
            "수축기": ["헬스케어", "유틸리티", "필수소비재"],
            "침체기": ["헬스케어", "유틸리티", "필수소비재"],
        }
    },
    "채권": {
        "icon": "📊",
        "description": "안정적인 이자 수익 추구",
        "etfs": [
            {"ticker": "BND", "name": "Vanguard Total Bond Market", "expense": 0.03},
            {"ticker": "TLT", "name": "iShares 20+ Year Treasury", "expense": 0.15},
            {"ticker": "LQD", "name": "iShares Investment Grade Corporate", "expense": 0.14},
            {"ticker": "HYG", "name": "iShares High Yield Corporate", "expense": 0.48},
            {"ticker": "TIP", "name": "iShares TIPS Bond (물가연동)", "expense": 0.19},
        ],
        "recommendation_by_cycle": {
            "회복기": "단기채 → 중기채로 전환, 회사채 비중 확대",
            "확장기": "회사채/하이일드 선호, 금리 상승 대비",
            "과열기": "단기채 위주, 금리 상승 헤지",
            "수축기": "장기 국채 확대, 안전자산 선호",
            "침체기": "장기 국채 집중, 금리 인하 수혜",
        }
    },
    "금": {
        "icon": "🥇",
        "description": "인플레이션 헤지 & 안전자산",
        "etfs": [
            {"ticker": "GLD", "name": "SPDR Gold Shares", "expense": 0.40},
            {"ticker": "IAU", "name": "iShares Gold Trust", "expense": 0.25},
            {"ticker": "SGOL", "name": "Aberdeen Physical Gold", "expense": 0.17},
        ],
        "recommendation_by_cycle": {
            "회복기": "비중 축소, 위험자산 선호 시기",
            "확장기": "소량 유지, 포트폴리오 다각화",
            "과열기": "비중 확대, 인플레이션 헤지",
            "수축기": "비중 확대, 불확실성 대비",
            "침체기": "최대 비중, 안전자산 수요 급증",
        }
    },
    "현금": {
        "icon": "💵",
        "description": "유동성 확보 & 기회 대기",
        "etfs": [
            {"ticker": "SHV", "name": "iShares Short Treasury Bond", "expense": 0.15},
            {"ticker": "BIL", "name": "SPDR 1-3 Month T-Bill", "expense": 0.14},
            {"ticker": "SGOV", "name": "iShares 0-3 Month Treasury", "expense": 0.05},
        ],
        "recommendation_by_cycle": {
            "회복기": "최소 유지 (5%), 투자 기회 활용",
            "확장기": "최소 유지 (5-10%), 적극 투자",
            "과열기": "비중 확대 (10-15%), 조정 대비",
            "수축기": "비중 확대 (15-20%), 저가 매수 준비",
            "침체기": "적정 유지 (10-15%), 점진적 투자",
        }
    },
    "원자재": {
        "icon": "🛢️",
        "description": "인플레이션 헤지 & 경기 민감",
        "etfs": [
            {"ticker": "DBC", "name": "Invesco DB Commodity Index", "expense": 0.85},
            {"ticker": "GSG", "name": "iShares S&P GSCI Commodity", "expense": 0.75},
            {"ticker": "PDBC", "name": "Invesco Optimum Yield Diversified", "expense": 0.59},
        ],
        "recommendation_by_cycle": {
            "회복기": "비중 확대, 경기 회복 수혜",
            "확장기": "적정 유지, 수요 증가 기대",
            "과열기": "최대 비중, 인플레이션 헤지",
            "수축기": "비중 축소, 수요 감소 예상",
            "침체기": "최소 유지, 경기 침체로 수요 감소",
        }
    },
    "부동산": {
        "icon": "🏠",
        "description": "배당 수익 & 인플레이션 헤지",
        "etfs": [
            {"ticker": "VNQ", "name": "Vanguard Real Estate ETF", "expense": 0.12},
            {"ticker": "IYR", "name": "iShares US Real Estate", "expense": 0.39},
            {"ticker": "XLRE", "name": "Real Estate Select SPDR", "expense": 0.09},
        ],
        "recommendation_by_cycle": {
            "회복기": "비중 확대, 저금리 수혜",
            "확장기": "적정 유지, 임대 수요 증가",
            "과열기": "비중 축소, 금리 상승 압박",
            "수축기": "비중 축소, 경기 민감",
            "침체기": "선별 투자, 필수 부동산 위주",
        }
    }
}

