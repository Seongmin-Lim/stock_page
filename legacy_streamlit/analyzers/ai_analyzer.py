"""
AI 기반 주식 분석 모듈
Grok, Gemini, OpenAI GPT, Anthropic Claude, GitHub Models 지원
"""
import json
from datetime import datetime
from typing import Dict, Optional, List
import os
from dotenv import load_dotenv

# anthropic 모듈 사전 import (fallback용)
try:
    import anthropic
except ImportError:
    anthropic = None

load_dotenv()


class AIAnalyzer:
    """AI 기반 주식 분석 클래스"""
    
    SUPPORTED_PROVIDERS = ["grok", "gemini", "openai", "anthropic", "github"]
    
    # GitHub Models 사용 가능 모델
    GITHUB_MODELS = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "llama-3.1-405b": "Meta-Llama-3.1-405B-Instruct",
        "llama-3.1-70b": "Meta-Llama-3.1-70B-Instruct",
        "llama-3.1-8b": "Meta-Llama-3.1-8B-Instruct",
        "mistral-large": "Mistral-Large-2411",
        "mistral-small": "Mistral-Small",
        "phi-4": "Phi-4",
        "cohere-command-r-plus": "Cohere-command-r-plus",
    }
    
    def __init__(self, provider: str = "grok", model: str = None):
        self.provider = provider.lower()
        self.model = model or self._get_default_model()
        self.client = self._initialize_client()
    
    def _get_default_model(self) -> str:
        """기본 모델 설정"""
        defaults = {
            "grok": "grok-beta",
            "gemini": "gemini-1.5-pro",
            "openai": "gpt-4o",
            "anthropic": "claude-sonnet-4-20250514",
            "github": "gpt-4o-mini",  # GitHub Models 기본 모델
        }
        return defaults.get(self.provider, "grok-beta")
    
    def _initialize_client(self):
        """AI 클라이언트 초기화"""
        if self.provider == "grok":
            try:
                from openai import OpenAI
                api_key = os.getenv("GROK_API_KEY")
                if not api_key:
                    print("⚠️ GROK_API_KEY가 설정되지 않았습니다.")
                    return None
                return OpenAI(
                    api_key=api_key,
                    base_url="https://api.x.ai/v1"
                )
            except ImportError:
                print("OpenAI 라이브러리를 설치해주세요: pip install openai")
                return None
        
        elif self.provider == "gemini":
            try:
                from google import genai
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
                    return None
                client = genai.Client(api_key=api_key)
                return client
            except ImportError:
                try:
                    # Fallback to old API
                    import google.generativeai as genai
                    api_key = os.getenv("GEMINI_API_KEY")
                    if not api_key:
                        print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
                        return None
                    genai.configure(api_key=api_key)
                    return genai.GenerativeModel(self.model)
                except ImportError:
                    print("Google AI 라이브러리를 설치해주세요: pip install google-genai")
                    return None
        
        elif self.provider == "openai":
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    print("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")
                    return None
                return OpenAI(api_key=api_key)
            except ImportError:
                print("OpenAI 라이브러리를 설치해주세요: pip install openai")
                return None
        
        elif self.provider == "anthropic":
            try:
                import anthropic
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    print("⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
                    return None
                return anthropic.Anthropic(api_key=api_key)
            except ImportError:
                print("Anthropic 라이브러리를 설치해주세요: pip install anthropic")
                return None
        
        elif self.provider == "github":
            try:
                from openai import OpenAI
                api_key = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
                if not api_key:
                    print("⚠️ GITHUB_TOKEN 또는 GITHUB_PAT가 설정되지 않았습니다.")
                    return None
                # GitHub Models용 모델명 매핑
                if self.model in self.GITHUB_MODELS:
                    self.model = self.GITHUB_MODELS[self.model]
                return OpenAI(
                    api_key=api_key,
                    base_url="https://models.github.ai/inference"  # 올바른 엔드포인트
                )
            except ImportError:
                print("OpenAI 라이브러리를 설치해주세요: pip install openai")
                return None
        
        return None
    
    def _init_github_client(self):
        """GitHub Models 클라이언트 초기화 (fallback용)"""
        try:
            from openai import OpenAI
            api_key = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
            if not api_key:
                return None
            return OpenAI(
                api_key=api_key,
                base_url="https://models.github.ai/inference"  # 올바른 엔드포인트
            )
        except:
            return None
    
    def _call_ai(self, system_prompt: str, user_prompt: str) -> str:
        """
        AI API 호출 - GitHub Models 1순위, 실패시 원래 provider로 fallback
        
        우선순위:
        1. GitHub Models (무료)
        2. 지정된 provider의 자체 API (유료)
        """
        
        # 1순위: GitHub Models 시도 (github provider가 아닌 경우만)
        if self.provider != "github":
            github_client = self._init_github_client()
            if github_client:
                try:
                    github_model = "gpt-4o-mini"  # 무료 모델 사용
                    response = github_client.chat.completions.create(
                        model=github_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=4000
                    )
                    result = response.choices[0].message.content
                    if result:
                        print(f"✅ [{self.provider}] GitHub Models로 응답 성공")
                        return result
                except Exception as e:
                    print(f"⚠️ [{self.provider}] GitHub Models 실패, fallback 시도: {e}")
        
        # 2순위: 원래 지정된 provider 사용
        if not self.client:
            return f"AI 클라이언트가 초기화되지 않았습니다. ({self.provider})"
        
        try:
            if self.provider in ["grok", "openai", "github"]:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                result = response.choices[0].message.content
                print(f"✅ [{self.provider}] 자체 API로 응답 성공")
                return result
            
            elif self.provider == "gemini":
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                # 새 google.genai API 사용
                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=full_prompt
                    )
                    print(f"✅ [{self.provider}] 자체 API로 응답 성공")
                    return response.text
                except AttributeError:
                    # 구 API fallback
                    response = self.client.generate_content(full_prompt)
                    print(f"✅ [{self.provider}] 자체 API로 응답 성공")
                    return response.text
            
            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                print(f"✅ [{self.provider}] 자체 API로 응답 성공")
                return response.content[0].text
        
        except Exception as e:
            print(f"⚠️ [{self.provider}] API 호출 실패: {e}")
            
            # 3순위 (최종 fallback): Claude API
            claude_result = self._fallback_to_claude(system_prompt, user_prompt)
            if claude_result:
                return claude_result
            
            return f"AI 분석 중 오류 발생: {str(e)}"
    
    def _fallback_to_claude(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """최종 fallback: Claude API 직접 호출"""
        if anthropic is None:
            print("⚠️ anthropic 모듈 미설치 - Claude fallback 불가")
            return None
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("your_"):
            return None
        
        try:
            client = anthropic.Anthropic(api_key=api_key)
            
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            result = response.content[0].text
            print(f"✅ Claude API fallback 성공 (원래 provider: {self.provider})")
            return result
        
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                print(f"⚠️ Claude API 크레딧 부족 - fallback 건너뜀")
            else:
                print(f"⚠️ Claude API 요청 오류: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Claude API fallback 실패: {e}")
            return None
    
    def analyze_market_conditions(self, market_data: Dict, economic_cycle: Dict = None) -> str:
        """시장 상황 종합 분석"""
        system_prompt = """당신은 전문 금융 애널리스트입니다. 
주어진 시장 데이터를 분석하여 현재 시장 상황에 대한 종합적인 의견을 제시해주세요.
한국어로 답변하며, 다음 형식을 따라주세요:

1. 📊 현재 시장 상태 요약
2. 📈 주요 지표 분석 (VIX, 금리, 공포탐욕 지수 등)
3. 🔄 경제 사이클 위치 및 의미
4. 💭 투자 심리 판단
5. ⚠️ 리스크 요인
6. 💡 투자 전략 제안
"""
        
        economic_info = ""
        if economic_cycle:
            economic_info = f"\n\n경제 사이클 분석:\n{json.dumps(economic_cycle, indent=2, ensure_ascii=False, default=str)}"
        
        user_prompt = f"""다음 시장 데이터를 분석해주세요:

{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}
{economic_info}

현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def analyze_with_news(self, market_data: Dict, news_data: Dict, economic_cycle: Dict = None) -> str:
        """뉴스를 포함한 종합 분석"""
        system_prompt = """당신은 전문 금융 애널리스트입니다.
시장 데이터와 최신 뉴스를 종합하여 분석해주세요.
한국어로 답변하며, 다음 형식을 따라주세요:

1. 📰 주요 뉴스 요약 및 시장 영향
2. 📊 현재 시장 상황
3. 🔄 경제 사이클 관점에서의 해석
4. 📈 뉴스가 시사하는 방향성
5. ⚠️ 주의해야 할 이슈
6. 💡 투자 전략 제안
"""
        
        economic_info = ""
        if economic_cycle:
            economic_info = f"\n\n경제 사이클 분석:\n- 현재 단계: {economic_cycle.get('current_phase', 'N/A')}\n- 신뢰도: {economic_cycle.get('confidence', 'N/A')}%"
        
        # 뉴스 요약 정리
        market_news = news_data.get('market_news', {}).get('articles', [])[:10]
        news_summary = "\n".join([f"- {n.get('title', '')}" for n in market_news])
        
        news_sentiment = news_data.get('market_news', {}).get('sentiment', {})
        
        user_prompt = f"""
시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}
{economic_info}

최근 주요 뉴스:
{news_summary}

뉴스 감성 분석:
- 감성: {news_sentiment.get('sentiment', 'N/A')}
- 점수: {news_sentiment.get('score', 'N/A')}
- 긍정 신호: {news_sentiment.get('positive_signals', 0)}개
- 부정 신호: {news_sentiment.get('negative_signals', 0)}개

현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def analyze_stock(self, stock_data: Dict, market_context: Dict = None, economic_cycle: Dict = None) -> str:
        """개별 주식 분석 (경제 사이클 반영)"""
        system_prompt = """당신은 전문 주식 애널리스트입니다.
주어진 주식 데이터를 분석하여 투자 의견을 제시해주세요.
현재 경제 사이클 단계에 맞춰 기준값을 조정하여 분석하세요.
한국어로 답변하며, 다음 형식을 따라주세요:

1. 🏢 기업 개요
2. 📊 밸류에이션 분석 (경제 사이클 반영 기준)
   - 현재 PER vs 조정된 적정 PER
   - 현재 PBR vs 조정된 적정 PBR
3. 💰 재무 건전성 평가
4. 📈 성장성 분석
5. 📉 기술적 위치 (52주 고저 대비)
6. 🎯 투자 의견 (매수/보유/매도)
7. 💵 목표가 및 리스크
"""
        
        context_info = ""
        if market_context:
            context_info = f"\n\n현재 시장 상황:\n{json.dumps(market_context, indent=2, ensure_ascii=False, default=str)}"
        
        cycle_info = ""
        if economic_cycle:
            cycle_info = f"""
\n경제 사이클 정보:
- 현재 단계: {economic_cycle.get('current_phase', 'N/A')}
- 조정된 적정 PER: {economic_cycle.get('dynamic_adjustments', {}).get('adjusted_per_fair', 20)}
- VIX 경계선: {economic_cycle.get('dynamic_adjustments', {}).get('adjusted_vix_threshold', 25)}
"""
        
        user_prompt = f"""다음 주식을 분석해주세요:

{json.dumps(stock_data, indent=2, ensure_ascii=False, default=str)}
{context_info}
{cycle_info}

현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def analyze_portfolio_comparison(self, portfolio_comparison: Dict, economic_cycle: Dict = None) -> str:
        """포트폴리오 비교 분석"""
        system_prompt = """당신은 포트폴리오 관리 전문가입니다.
사용자의 포트폴리오를 레이 달리오의 올웨더 포트폴리오, 워렌 버핏의 추천 포트폴리오 등
유명 투자 전략과 비교 분석해주세요.
한국어로 답변하며, 다음 형식을 따라주세요:

1. 📊 포트폴리오 성과 요약
2. 🆚 유명 포트폴리오와의 비교
   - 올웨더 포트폴리오 대비
   - 60/40 포트폴리오 대비
   - 기타 전략 대비
3. 💪 강점 분석
4. ⚠️ 약점 및 리스크
5. 🔄 현재 경제 사이클에서의 적합성
6. 💡 개선 제안
"""
        
        cycle_info = ""
        if economic_cycle:
            cycle_info = f"""
경제 사이클 정보:
- 현재 단계: {economic_cycle.get('current_phase', 'N/A')}
- 추천 자산 배분: {json.dumps(economic_cycle.get('recommendations', {}).get('asset_allocation', {}), ensure_ascii=False)}
- 추천 섹터: {', '.join(economic_cycle.get('recommendations', {}).get('sectors', []))}
"""
        
        user_prompt = f"""
포트폴리오 비교 분석 데이터:
{json.dumps(portfolio_comparison, indent=2, ensure_ascii=False, default=str)}

{cycle_info}

현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def compare_stocks(self, stocks_data: List[Dict], economic_cycle: Dict = None) -> str:
        """여러 주식 비교 분석"""
        system_prompt = """당신은 전문 주식 애널리스트입니다.
주어진 여러 주식을 비교 분석하여 투자 우선순위를 제시해주세요.
현재 경제 사이클을 고려하여 분석해주세요.
한국어로 답변하며, 다음 형식을 따라주세요:

1. 📋 비교 대상 기업 요약
2. 📊 밸류에이션 비교표
3. 📈 성장성 비교
4. 💰 수익성 비교
5. ⚠️ 리스크 비교
6. 🏆 현재 경제 단계에서의 종합 순위 및 추천
"""
        
        cycle_info = ""
        if economic_cycle:
            cycle_info = f"\n현재 경제 단계: {economic_cycle.get('current_phase', 'N/A')}"
            cycle_info += f"\n추천 섹터: {', '.join(economic_cycle.get('recommendations', {}).get('sectors', []))}"
        
        user_prompt = f"""다음 주식들을 비교 분석해주세요:

{json.dumps(stocks_data, indent=2, ensure_ascii=False, default=str)}
{cycle_info}

현재 날짜: {datetime.now().strftime('%Y년 %m월 %d일')}
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def analyze_fear_greed(self, fear_greed_data: Dict) -> str:
        """공포탐욕 지수 분석"""
        system_prompt = """당신은 행동 금융학 전문가입니다.
공포탐욕 지수와 구성 요소를 분석하여 현재 투자 심리와 전략을 제시해주세요.
한국어로 답변해주세요.
"""
        
        user_prompt = f"""현재 공포탐욕 지수 데이터:

{json.dumps(fear_greed_data, indent=2, ensure_ascii=False, default=str)}

1. 현재 지수가 의미하는 바
2. 과거 유사 구간에서의 시장 움직임
3. 역발상 투자 관점에서의 해석
4. 단기/중기 전략 제안
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def generate_portfolio_recommendation(self, 
                                         market_data: Dict,
                                         fear_greed: Dict,
                                         stocks_data: List[Dict],
                                         economic_cycle: Dict,
                                         risk_tolerance: str = "moderate") -> str:
        """포트폴리오 추천 (경제 사이클 반영)"""
        system_prompt = """당신은 공인 재무설계사(CFP)입니다.
주어진 시장 상황, 경제 사이클, 개별 주식 데이터를 바탕으로 포트폴리오를 추천해주세요.
한국어로 답변하며, 투자자의 위험 성향과 현재 경제 단계를 고려해주세요.
"""
        
        risk_profiles = {
            "conservative": "보수적 (원금 보존 중시, 변동성 최소화)",
            "moderate": "중립적 (적정 수익과 리스크 균형)",
            "aggressive": "공격적 (높은 수익 추구, 변동성 감수)"
        }
        
        user_prompt = f"""
투자자 위험 성향: {risk_profiles.get(risk_tolerance, risk_profiles['moderate'])}

현재 경제 사이클:
- 단계: {economic_cycle.get('current_phase', 'N/A')}
- 신뢰도: {economic_cycle.get('confidence', 'N/A')}%
- 추천 섹터: {', '.join(economic_cycle.get('recommendations', {}).get('sectors', []))}
- 추천 배분: {json.dumps(economic_cycle.get('recommendations', {}).get('asset_allocation', {}), ensure_ascii=False)}

시장 전망:
{json.dumps(economic_cycle.get('market_outlook', {}), indent=2, ensure_ascii=False)}

현재 시장 상황:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

공포탐욕 지수:
{json.dumps(fear_greed, indent=2, ensure_ascii=False, default=str)}

분석 대상 주식:
{json.dumps(stocks_data, indent=2, ensure_ascii=False, default=str)}

다음을 포함하여 포트폴리오를 추천해주세요:
1. 현재 시장 및 경제 사이클 진단
2. 자산 배분 전략 (주식/채권/현금/대안자산 비율)
3. 추천 종목과 비중
4. 유명 포트폴리오(올웨더 등)와의 차이점
5. 리밸런싱 시점
6. 주의사항 및 리스크 관리
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def explain_economic_cycle(self, economic_cycle: Dict) -> str:
        """경제 사이클 상세 설명"""
        system_prompt = """당신은 거시경제 전문가입니다.
현재 경제 사이클 단계에 대해 쉽게 설명하고, 투자 전략을 제시해주세요.
한국어로 답변해주세요.
"""
        
        user_prompt = f"""현재 경제 사이클 분석 결과:

{json.dumps(economic_cycle, indent=2, ensure_ascii=False, default=str)}

다음을 설명해주세요:
1. 현재 경제 단계의 특징
2. 이 단계에서 일반적으로 나타나는 현상
3. 다음 단계로의 전환 신호
4. 이 단계에서의 투자 전략
5. 피해야 할 자산/섹터
6. 주목해야 할 자산/섹터
"""
        
        return self._call_ai(system_prompt, user_prompt)
    
    def explain_indicator(self, indicator_name: str, current_value: float) -> str:
        """지표 설명"""
        system_prompt = """당신은 금융 교육 전문가입니다.
주어진 금융 지표에 대해 쉽게 설명해주세요.
한국어로 답변해주세요.
"""
        
        user_prompt = f"""
'{indicator_name}' 지표에 대해 설명해주세요.
현재 값: {current_value}

1. 지표의 정의
2. 계산 방법
3. 해석 방법
4. 현재 값의 의미
5. 투자에 활용하는 방법
"""
        
        return self._call_ai(system_prompt, user_prompt)


if __name__ == "__main__":
    # 테스트
    print("=== AI Analyzer 테스트 ===")
    print(f"지원 제공자: {AIAnalyzer.SUPPORTED_PROVIDERS}")
    
    # Grok 테스트
    analyzer = AIAnalyzer(provider="grok")
    print(f"\n현재 제공자: {analyzer.provider}")
    print(f"현재 모델: {analyzer.model}")
    
    if analyzer.client:
        print("✅ 클라이언트 초기화 성공")
    else:
        print("⚠️ 클라이언트 초기화 실패 - API 키를 확인하세요")
