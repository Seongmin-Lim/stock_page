"""
경제 사이클 분석 모듈
현재 경제 상태 (회복기, 확장기, 과열기, 침체기) 판단
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum


class EconomicPhase(Enum):
    """경제 사이클 단계"""
    RECOVERY = "회복기"      # Recovery - 저점에서 회복 중
    EXPANSION = "확장기"     # Expansion - 성장 가속화
    PEAK = "과열기"          # Peak/Overheat - 정점 근처
    CONTRACTION = "수축기"   # Contraction - 하락 중
    TROUGH = "침체기"        # Trough/Recession - 저점


class EconomicCycleAnalyzer:
    """경제 사이클 분석 클래스"""
    
    # 각 경제 단계별 특성 기준값
    PHASE_CHARACTERISTICS = {
        EconomicPhase.RECOVERY: {
            "description": "경기 저점 통과 후 회복 단계. 금리 낮음, 실업률 감소 시작",
            "vix_range": (20, 35),
            "yield_curve": "steepening",  # 금리 곡선 가팔라짐
            "market_trend": "early_bull",
            "recommended_sectors": ["금융", "부동산", "소비재", "산업재"],
            "asset_allocation": {"주식": 60, "채권": 30, "현금": 5, "원자재": 5}
        },
        EconomicPhase.EXPANSION: {
            "description": "경기 확장 단계. 기업 실적 개선, 고용 증가",
            "vix_range": (12, 20),
            "yield_curve": "normal",
            "market_trend": "bull",
            "recommended_sectors": ["기술", "소비재", "산업재", "헬스케어"],
            "asset_allocation": {"주식": 70, "채권": 20, "현금": 5, "원자재": 5}
        },
        EconomicPhase.PEAK: {
            "description": "경기 과열 단계. 인플레이션 상승, 금리 인상",
            "vix_range": (10, 15),
            "yield_curve": "flattening",  # 금리 곡선 평탄화
            "market_trend": "late_bull",
            "recommended_sectors": ["에너지", "소재", "유틸리티"],
            "asset_allocation": {"주식": 50, "채권": 25, "현금": 15, "원자재": 10}
        },
        EconomicPhase.CONTRACTION: {
            "description": "경기 수축 단계. 기업 실적 악화, 신용 경색",
            "vix_range": (25, 45),
            "yield_curve": "inverted",  # 역전
            "market_trend": "bear",
            "recommended_sectors": ["유틸리티", "헬스케어", "필수소비재"],
            "asset_allocation": {"주식": 30, "채권": 40, "현금": 25, "원자재": 5}
        },
        EconomicPhase.TROUGH: {
            "description": "경기 침체 저점. 금리 인하, 경기 부양책",
            "vix_range": (30, 60),
            "yield_curve": "steepening",
            "market_trend": "bottom",
            "recommended_sectors": ["필수소비재", "유틸리티", "헬스케어"],
            "asset_allocation": {"주식": 40, "채권": 35, "현금": 20, "원자재": 5}
        }
    }
    
    # 동적 기준값 조정 계수
    DYNAMIC_ADJUSTMENTS = {
        EconomicPhase.RECOVERY: {"per_adjustment": 0.9, "vix_tolerance": 1.2},
        EconomicPhase.EXPANSION: {"per_adjustment": 1.0, "vix_tolerance": 1.0},
        EconomicPhase.PEAK: {"per_adjustment": 1.1, "vix_tolerance": 0.8},
        EconomicPhase.CONTRACTION: {"per_adjustment": 0.85, "vix_tolerance": 1.3},
        EconomicPhase.TROUGH: {"per_adjustment": 0.8, "vix_tolerance": 1.5},
    }
    
    def __init__(self):
        self.cache = {}
    
    def analyze_economic_cycle(self) -> Dict:
        """현재 경제 사이클 분석"""
        indicators = self._collect_indicators()
        phase = self._determine_phase(indicators)
        confidence = self._calculate_confidence(indicators, phase)
        
        phase_info = self.PHASE_CHARACTERISTICS[phase]
        adjustments = self.DYNAMIC_ADJUSTMENTS[phase]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_phase": phase.value,
            "phase_enum": phase.name,
            "confidence": round(confidence * 100, 1),
            "description": phase_info["description"],
            "indicators": indicators,
            "recommendations": {
                "sectors": phase_info["recommended_sectors"],
                "asset_allocation": phase_info["asset_allocation"],
            },
            "dynamic_adjustments": {
                "per_multiplier": adjustments["per_adjustment"],
                "vix_tolerance": adjustments["vix_tolerance"],
                "adjusted_per_fair": round(20 * adjustments["per_adjustment"], 1),
                "adjusted_vix_threshold": round(20 * adjustments["vix_tolerance"], 1),
            },
            "market_outlook": self._get_market_outlook(phase),
        }
    
    def _collect_indicators(self) -> Dict:
        """경제 지표 수집"""
        indicators = {}
        
        # 1. VIX (변동성)
        try:
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period="3mo")
            indicators["vix"] = {
                "current": vix_data['Close'].iloc[-1],
                "avg_3m": vix_data['Close'].mean(),
                "trend": "상승" if vix_data['Close'].iloc[-1] > vix_data['Close'].iloc[-20] else "하락"
            }
        except:
            indicators["vix"] = {"current": 20, "avg_3m": 20, "trend": "N/A"}
        
        # 2. 금리 곡선 (10년 - 2년)
        try:
            tnx = yf.Ticker("^TNX")  # 10년
            tnx_data = tnx.history(period="1mo")
            rate_10y = tnx_data['Close'].iloc[-1]
            
            # 2년 금리 대리 (약식 계산)
            irx = yf.Ticker("^IRX")  # 13주 T-Bill
            irx_data = irx.history(period="1mo")
            rate_short = irx_data['Close'].iloc[-1] if not irx_data.empty else rate_10y - 0.5
            
            spread = rate_10y - rate_short
            
            if spread > 1.5:
                curve_status = "steep"
            elif spread > 0.5:
                curve_status = "normal"
            elif spread > 0:
                curve_status = "flat"
            else:
                curve_status = "inverted"
            
            indicators["yield_curve"] = {
                "10y_rate": rate_10y,
                "short_rate": rate_short,
                "spread": round(spread, 2),
                "status": curve_status
            }
        except:
            indicators["yield_curve"] = {"spread": 1.0, "status": "normal"}
        
        # 3. S&P 500 트렌드
        try:
            sp500 = yf.Ticker("^GSPC")
            sp_data = sp500.history(period="1y")
            
            current = sp_data['Close'].iloc[-1]
            ma_50 = sp_data['Close'].rolling(50).mean().iloc[-1]
            ma_200 = sp_data['Close'].rolling(200).mean().iloc[-1]
            high_52w = sp_data['High'].max()
            low_52w = sp_data['Low'].min()
            
            # 52주 범위 내 위치 (0-100%)
            position = ((current - low_52w) / (high_52w - low_52w)) * 100
            
            # 트렌드 판단
            if current > ma_50 > ma_200:
                trend = "strong_uptrend"
            elif current > ma_200:
                trend = "uptrend"
            elif current < ma_50 < ma_200:
                trend = "strong_downtrend"
            else:
                trend = "downtrend"
            
            indicators["market_trend"] = {
                "current": current,
                "ma_50": ma_50,
                "ma_200": ma_200,
                "52w_position": round(position, 1),
                "trend": trend,
                "above_ma200": current > ma_200
            }
        except:
            indicators["market_trend"] = {"trend": "neutral", "52w_position": 50}
        
        # 4. 시장 밸류에이션 (SPY Forward PE)
        try:
            spy = yf.Ticker("SPY")
            info = spy.info
            indicators["valuation"] = {
                "forward_pe": info.get("forwardPE"),
                "trailing_pe": info.get("trailingPE"),
            }
        except:
            indicators["valuation"] = {"forward_pe": 20, "trailing_pe": 22}
        
        # 5. 변동성 추세
        try:
            vix_change = indicators["vix"]["current"] - indicators["vix"]["avg_3m"]
            indicators["volatility_trend"] = {
                "change_from_avg": round(vix_change, 2),
                "elevated": indicators["vix"]["current"] > 25,
                "extreme": indicators["vix"]["current"] > 35
            }
        except:
            indicators["volatility_trend"] = {"elevated": False, "extreme": False}
        
        return indicators
    
    def _determine_phase(self, indicators: Dict) -> EconomicPhase:
        """경제 단계 결정"""
        scores = {phase: 0 for phase in EconomicPhase}
        
        vix = indicators.get("vix", {}).get("current", 20)
        yield_curve = indicators.get("yield_curve", {}).get("status", "normal")
        market_trend = indicators.get("market_trend", {}).get("trend", "neutral")
        position = indicators.get("market_trend", {}).get("52w_position", 50)
        
        # VIX 기반 점수
        if vix < 15:
            scores[EconomicPhase.PEAK] += 2
            scores[EconomicPhase.EXPANSION] += 1
        elif vix < 20:
            scores[EconomicPhase.EXPANSION] += 2
        elif vix < 25:
            scores[EconomicPhase.RECOVERY] += 1
            scores[EconomicPhase.CONTRACTION] += 1
        elif vix < 35:
            scores[EconomicPhase.CONTRACTION] += 2
            scores[EconomicPhase.RECOVERY] += 1
        else:
            scores[EconomicPhase.TROUGH] += 3
        
        # 금리 곡선 기반 점수
        if yield_curve == "steep":
            scores[EconomicPhase.RECOVERY] += 2
        elif yield_curve == "normal":
            scores[EconomicPhase.EXPANSION] += 2
        elif yield_curve == "flat":
            scores[EconomicPhase.PEAK] += 2
        elif yield_curve == "inverted":
            scores[EconomicPhase.CONTRACTION] += 3
        
        # 시장 트렌드 기반 점수
        if market_trend == "strong_uptrend":
            scores[EconomicPhase.EXPANSION] += 2
            if position > 90:
                scores[EconomicPhase.PEAK] += 1
        elif market_trend == "uptrend":
            scores[EconomicPhase.EXPANSION] += 1
            scores[EconomicPhase.RECOVERY] += 1
        elif market_trend == "strong_downtrend":
            scores[EconomicPhase.CONTRACTION] += 2
            if position < 20:
                scores[EconomicPhase.TROUGH] += 2
        elif market_trend == "downtrend":
            scores[EconomicPhase.CONTRACTION] += 1
        
        # 52주 위치 기반 조정
        if position > 85:
            scores[EconomicPhase.PEAK] += 1
        elif position < 25:
            scores[EconomicPhase.TROUGH] += 1
            scores[EconomicPhase.RECOVERY] += 1
        
        # 최고 점수 단계 반환
        return max(scores, key=scores.get)
    
    def _calculate_confidence(self, indicators: Dict, phase: EconomicPhase) -> float:
        """판단 신뢰도 계산"""
        # 지표들의 일관성 체크
        consistency_score = 0
        total_checks = 0
        
        vix = indicators.get("vix", {}).get("current", 20)
        yield_curve = indicators.get("yield_curve", {}).get("status", "normal")
        market_trend = indicators.get("market_trend", {}).get("trend", "neutral")
        
        phase_chars = self.PHASE_CHARACTERISTICS[phase]
        vix_range = phase_chars["vix_range"]
        
        # VIX 범위 체크
        total_checks += 1
        if vix_range[0] <= vix <= vix_range[1]:
            consistency_score += 1
        elif abs(vix - sum(vix_range)/2) < 10:
            consistency_score += 0.5
        
        # 금리 곡선 체크
        total_checks += 1
        expected_curve = phase_chars["yield_curve"]
        if yield_curve == expected_curve:
            consistency_score += 1
        elif yield_curve in ["normal", "steepening"] and expected_curve in ["normal", "steepening"]:
            consistency_score += 0.5
        
        # 시장 트렌드 체크
        total_checks += 1
        expected_trend = phase_chars["market_trend"]
        trend_mapping = {
            "early_bull": ["uptrend", "strong_uptrend"],
            "bull": ["strong_uptrend", "uptrend"],
            "late_bull": ["uptrend"],
            "bear": ["downtrend", "strong_downtrend"],
            "bottom": ["strong_downtrend", "downtrend"]
        }
        if market_trend in trend_mapping.get(expected_trend, []):
            consistency_score += 1
        
        return consistency_score / total_checks if total_checks > 0 else 0.5
    
    def _get_market_outlook(self, phase: EconomicPhase) -> Dict:
        """전문적인 시장 전망 분석"""
        outlooks = {
            EconomicPhase.RECOVERY: {
                "macro_view": """경기 저점 통과 후 초기 회복 국면 진입. 중앙은행의 완화적 통화정책이 유지되고 있으며, 
                신용 스프레드 축소와 함께 위험자산 선호도가 점진적으로 개선되고 있습니다. 
                기업 실적 바닥 확인 후 어닝 서프라이즈 가능성이 높아지는 시기입니다.""",
                "short_term": "긍정적 전망 - 저점 확인 후 반등 모멘텀 형성, 기술적 반등 기대",
                "medium_term": "강세 전환 예상 - 펀더멘털 개선과 함께 상승 사이클 초입",
                "long_term": "새로운 강세장의 시작 가능성. 조기 진입 시 높은 수익률 기대",
                "risk_factors": ["경기 회복 지연 가능성", "더블딥 리스크", "통화정책 전환 타이밍"],
                "opportunity_factors": ["저평가 우량주 매수 기회", "경기민감주 반등", "금융주 실적 개선"],
                "key_indicators": ["ISM 제조업 PMI 반등", "신규 실업수당 청구 감소", "소비자 신뢰지수 개선"],
                "strategy": """점진적 위험자산 비중 확대 권고. 경기민감 섹터(금융, 산업재, 소비재)에 대한 
                전략적 비중 확대를 고려하되, 분할 매수를 통해 리스크를 관리할 것을 권장합니다. 
                채권 듀레이션 축소를 고려할 시점입니다.""",
                "risk_level": "중간 (기회 우위)",
                "conviction": "높음"
            },
            EconomicPhase.EXPANSION: {
                "macro_view": """경기 확장 국면 지속. 기업 실적이 지속적으로 개선되고 있으며, 고용시장이 견조합니다. 
                중앙은행은 점진적 정상화 경로를 모색 중이나, 아직 긴축적이지 않습니다. 
                글로벌 성장 동조화와 함께 위험자산에 유리한 환경이 조성되어 있습니다.""",
                "short_term": "긍정적 전망 - 상승 추세 지속, 신고가 경신 가능",
                "medium_term": "지속적 강세 예상 - 실적 성장이 밸류에이션 부담을 상쇄",
                "long_term": "확장 국면 후반기 진입 시 조정 가능성 대비 필요",
                "risk_factors": ["밸류에이션 부담 누적", "금리 인상 우려", "지정학적 리스크"],
                "opportunity_factors": ["기업 실적 모멘텀 지속", "M&A 활성화", "IPO 시장 호황"],
                "key_indicators": ["기업 실적 성장률", "CapEx 투자 증가", "CEO 신뢰지수"],
                "strategy": """위험자산 비중 유지 또는 확대. 성장주 중심의 포트폴리오 구성이 유효하며, 
                특히 이익 성장률이 높은 기술주와 경기소비재에 주목할 필요가 있습니다. 
                다만, 과열 신호 모니터링을 통해 점진적 이익실현 타이밍을 고려해야 합니다.""",
                "risk_level": "낮음-중간",
                "conviction": "매우 높음"
            },
            EconomicPhase.PEAK: {
                "macro_view": """경기 사이클 후반부 진입. 인플레이션 압력이 가시화되고 중앙은행의 긴축 기조가 강화되고 있습니다. 
                노동시장 과열과 임금 상승 압력이 기업 마진을 압박하기 시작했으며, 
                금리 상승으로 밸류에이션 리레이팅(하향 조정) 압력이 존재합니다.""",
                "short_term": "중립-부정적 전망 - 상승 탄력 둔화, 변동성 확대 예상",
                "medium_term": "조정 가능성 상승 - 실적 피크아웃 우려",
                "long_term": "사이클 전환점 접근, 방어적 포지셔닝 필요",
                "risk_factors": ["인플레이션 고착화", "금리 급등", "신용 사이클 전환", "마진 압축"],
                "opportunity_factors": ["인플레이션 수혜 섹터", "필수재 기업", "배당주"],
                "key_indicators": ["Core CPI 추이", "임금 상승률", "회사채 스프레드"],
                "strategy": """방어적 포지셔닝 강화 권고. 성장주에서 가치주로의 로테이션을 고려하고, 
                에너지, 소재, 유틸리티 등 인플레이션 수혜 섹터 비중 확대가 유효합니다. 
                현금 비중을 10-15%로 높이고, 차익 실현을 적극 고려하시기 바랍니다.""",
                "risk_level": "높음",
                "conviction": "높음"
            },
            EconomicPhase.CONTRACTION: {
                "macro_view": """경기 수축 국면 진입 확인. 경제 지표가 광범위하게 악화되고 있으며, 
                기업 실적 하향 조정이 본격화되고 있습니다. 신용 경색 우려와 함께 
                위험자산 회피 심리가 팽배해지고 있으며, 변동성이 구조적으로 높은 상태입니다.""",
                "short_term": "부정적 전망 - 추가 하락 및 변동성 확대 예상",
                "medium_term": "신중한 관망 권고 - 저점 확인 전까지 방어적 스탠스 유지",
                "long_term": "사이클 저점 근접 시 장기 투자 기회",
                "risk_factors": ["실적 하향 사이클", "신용 경색", "유동성 위기", "시스템 리스크"],
                "opportunity_factors": ["방어주 상대 강세", "채권 가격 상승", "안전자산 수요"],
                "key_indicators": ["실업률 추이", "ISM PMI", "소비자 지출", "회사채 스프레드"],
                "strategy": """현금 및 채권 비중 확대 필수. 주식은 방어적 섹터(유틸리티, 헬스케어, 필수소비재)로 
                압축하고, 투자등급 회사채와 국채 비중을 높이시기 바랍니다. 
                레버리지 축소와 유동성 확보가 최우선 과제입니다.""",
                "risk_level": "매우 높음",
                "conviction": "높음"
            },
            EconomicPhase.TROUGH: {
                "macro_view": """경기 침체 저점 국면. 경제 지표가 최악 수준이나 악화 속도가 둔화되고 있습니다. 
                중앙은행의 적극적 완화 정책과 정부의 재정 부양책이 시행 중이며, 
                시장은 실물 경제보다 먼저 바닥을 형성할 가능성이 있습니다.""",
                "short_term": "변동성 극대화 - 저점 테스트 후 기술적 반등 시도",
                "medium_term": "역발상 매수 기회 - 장기 투자자에게 유리한 진입점",
                "long_term": "새로운 사이클 시작점, 적극적 비중 확대 검토",
                "risk_factors": ["침체 장기화", "디플레이션", "정책 실패", "2차 충격"],
                "opportunity_factors": ["극단적 저평가 종목", "구조조정 완료 기업", "정책 수혜주"],
                "key_indicators": ["선행지표 반등 신호", "신용스프레드 축소", "주가 바닥 패턴 형성"],
                "strategy": """역발상적 분할 매수 시작 권고. 우량 대형주와 배당주를 중심으로 3-6개월에 걸쳐 
                점진적 비중 확대를 시작하시기 바랍니다. 극도로 저평가된 경기민감주는 
                높은 변동성을 감수할 수 있는 투자자에게 매력적인 기회가 될 수 있습니다.""",
                "risk_level": "높음 (기회와 위험 공존)",
                "conviction": "중간-높음"
            }
        }
        return outlooks.get(phase, {})
    
    def get_adjusted_benchmarks(self) -> Dict:
        """경제 단계별 조정된 기준값 반환"""
        cycle_analysis = self.analyze_economic_cycle()
        phase = EconomicPhase[cycle_analysis["phase_enum"]]
        adjustments = self.DYNAMIC_ADJUSTMENTS[phase]
        
        # 기본 기준값
        base_benchmarks = {
            "per_fair": 20,
            "per_low": 15,
            "per_high": 25,
            "pbr_fair": 3.0,
            "vix_normal": 20,
            "vix_elevated": 25,
            "fear_greed_neutral": 50,
        }
        
        # 조정된 기준값
        adjusted = {
            "per_fair": round(base_benchmarks["per_fair"] * adjustments["per_adjustment"], 1),
            "per_low": round(base_benchmarks["per_low"] * adjustments["per_adjustment"], 1),
            "per_high": round(base_benchmarks["per_high"] * adjustments["per_adjustment"], 1),
            "pbr_fair": round(base_benchmarks["pbr_fair"] * adjustments["per_adjustment"], 2),
            "vix_normal": round(base_benchmarks["vix_normal"] * adjustments["vix_tolerance"], 1),
            "vix_elevated": round(base_benchmarks["vix_elevated"] * adjustments["vix_tolerance"], 1),
        }
        
        return {
            "economic_phase": cycle_analysis["current_phase"],
            "base_benchmarks": base_benchmarks,
            "adjusted_benchmarks": adjusted,
            "adjustment_rationale": f"{phase.value} 단계에서는 PER 기준 {adjustments['per_adjustment']}배, VIX 허용 범위 {adjustments['vix_tolerance']}배 적용"
        }


if __name__ == "__main__":
    analyzer = EconomicCycleAnalyzer()
    
    print("=== 경제 사이클 분석 ===")
    result = analyzer.analyze_economic_cycle()
    
    print(f"\n현재 경제 단계: {result['current_phase']}")
    print(f"신뢰도: {result['confidence']}%")
    print(f"설명: {result['description']}")
    
    print(f"\n추천 섹터: {', '.join(result['recommendations']['sectors'])}")
    print(f"자산 배분: {result['recommendations']['asset_allocation']}")
    
    print(f"\n동적 기준값:")
    for key, value in result['dynamic_adjustments'].items():
        print(f"  {key}: {value}")
    
    print(f"\n시장 전망:")
    for key, value in result['market_outlook'].items():
        print(f"  {key}: {value}")
