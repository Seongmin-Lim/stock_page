"""
🤖 AI 토론 시스템
Gemini와 Grok이 서로 분석 결과를 평가하고 수정하는 협업 시스템
"""
from typing import Dict, List, Optional, Generator
from dataclasses import dataclass
from enum import Enum
import json
import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AIRole(Enum):
    ANALYST = "analyst"      # 초기 분석가
    CRITIC = "critic"        # 비평가
    REVISER = "reviser"      # 수정자


@dataclass
class DebateRound:
    """토론 라운드 정보"""
    round_num: int
    analyst_ai: str
    critic_ai: str
    analysis: str
    critique: str
    revised_analysis: Optional[str] = None
    agreement_score: Optional[float] = None


class AIDebateSystem:
    """AI 토론 시스템 - 두 AI가 서로 분석을 평가하고 수정"""
    
    def __init__(self, primary_ai: str = "gemini", secondary_ai: str = "grok"):
        """
        Args:
            primary_ai: 초기 분석을 담당할 AI (gemini, grok, openai, anthropic)
            secondary_ai: 비평을 담당할 AI
        """
        self.primary_ai = primary_ai
        self.secondary_ai = secondary_ai
        self.debate_history: List[DebateRound] = []
        
        # AI 클라이언트 초기화 (AIAnalyzer 사용)
        self.ai_clients = {}
        self._init_ai_clients()
    
    def _init_ai_clients(self):
        """AI 클라이언트 초기화 - AIAnalyzer 사용"""
        from analyzers.ai_analyzer import AIAnalyzer
        
        # 모든 지원 AI 초기화
        providers = ['grok', 'gemini', 'openai', 'anthropic', 'github']
        
        for provider in providers:
            try:
                self.ai_clients[provider] = AIAnalyzer(provider=provider)
            except Exception as e:
                print(f"{provider} 초기화 실패: {e}")
    
    def _get_ai_client(self, ai_name: str):
        """AI 클라이언트 반환"""
        # 동적으로 초기화 (필요시)
        if ai_name not in self.ai_clients:
            try:
                from analyzers.ai_analyzer import AIAnalyzer
                self.ai_clients[ai_name] = AIAnalyzer(provider=ai_name)
            except Exception as e:
                print(f"{ai_name} 동적 초기화 실패: {e}")
                return None
        return self.ai_clients.get(ai_name)
    
    def _call_ai(self, ai_name: str, prompt: str) -> str:
        """
        AI 호출 - GitHub Models 1순위, 실패시 지정된 AI API로 fallback
        
        우선순위:
        1. GitHub Models (GITHUB_TOKEN으로 무료 사용)
        2. 지정된 AI의 자체 API (유료)
        """
        system_prompt = "당신은 전문 금융 분석가입니다. 정확하고 통찰력 있는 분석을 제공하세요."
        
        # 1순위: GitHub Models 시도
        github_client = self._get_ai_client('github')
        if github_client and github_client.client:
            try:
                result = github_client._call_ai(system_prompt, prompt)
                if result and "[오류]" not in result and "호출 실패" not in result:
                    print(f"✅ [{ai_name}] GitHub Models로 응답 성공")
                    return result
            except Exception as e:
                print(f"⚠️ [{ai_name}] GitHub Models 실패, fallback 시도: {e}")
        
        # 2순위: 지정된 AI의 자체 API로 fallback
        client = self._get_ai_client(ai_name)
        if not client:
            return f"[{ai_name} AI를 사용할 수 없습니다. API 키를 확인하세요.]"
        
        try:
            result = client._call_ai(system_prompt, prompt)
            print(f"✅ [{ai_name}] 자체 API로 응답 성공")
            return result
        except Exception as e:
            return f"[{ai_name} 호출 실패: {e}]"
    
    def run_market_debate(self, market_data: Dict, max_rounds: int = 3) -> Generator[Dict, None, None]:
        """
        시장 분석 토론 실행 (스트리밍)
        
        Args:
            market_data: 시장 데이터
            max_rounds: 최대 토론 라운드 수
            
        Yields:
            각 단계별 결과
        """
        self.debate_history = []
        
        # 1. 초기 분석 (Primary AI)
        yield {"stage": "initial_analysis", "ai": self.primary_ai, "status": "시작"}
        
        initial_prompt = self._create_market_analysis_prompt(market_data)
        initial_analysis = self._call_ai(self.primary_ai, initial_prompt)
        
        yield {
            "stage": "initial_analysis", 
            "ai": self.primary_ai, 
            "status": "완료",
            "content": initial_analysis
        }
        
        current_analysis = initial_analysis
        
        # 2. 토론 라운드
        for round_num in range(1, max_rounds + 1):
            yield {"stage": f"round_{round_num}", "status": "시작"}
            
            # 2-1. 비평 (Secondary AI)
            yield {"stage": f"round_{round_num}_critique", "ai": self.secondary_ai, "status": "비평 중"}
            
            critique_prompt = self._create_critique_prompt(current_analysis, self.primary_ai)
            critique = self._call_ai(self.secondary_ai, critique_prompt)
            
            yield {
                "stage": f"round_{round_num}_critique",
                "ai": self.secondary_ai,
                "status": "완료",
                "content": critique
            }
            
            # 2-2. 수정 (Primary AI)
            yield {"stage": f"round_{round_num}_revision", "ai": self.primary_ai, "status": "수정 중"}
            
            revision_prompt = self._create_revision_prompt(current_analysis, critique, self.secondary_ai)
            revised_analysis = self._call_ai(self.primary_ai, revision_prompt)
            
            yield {
                "stage": f"round_{round_num}_revision",
                "ai": self.primary_ai,
                "status": "완료",
                "content": revised_analysis
            }
            
            # 2-3. 합의 평가 (Secondary AI)
            yield {"stage": f"round_{round_num}_evaluation", "ai": self.secondary_ai, "status": "평가 중"}
            
            eval_prompt = self._create_evaluation_prompt(revised_analysis)
            evaluation = self._call_ai(self.secondary_ai, eval_prompt)
            
            # 합의 점수 추출
            agreement_score = self._extract_agreement_score(evaluation)
            
            yield {
                "stage": f"round_{round_num}_evaluation",
                "ai": self.secondary_ai,
                "status": "완료",
                "content": evaluation,
                "agreement_score": agreement_score
            }
            
            # 라운드 기록
            debate_round = DebateRound(
                round_num=round_num,
                analyst_ai=self.primary_ai,
                critic_ai=self.secondary_ai,
                analysis=current_analysis,
                critique=critique,
                revised_analysis=revised_analysis,
                agreement_score=agreement_score
            )
            self.debate_history.append(debate_round)
            
            current_analysis = revised_analysis
            
            # 합의 도달 시 조기 종료
            if agreement_score and agreement_score >= 85:
                yield {"stage": "consensus_reached", "score": agreement_score}
                break
            
            # AI 역할 교체 (다음 라운드)
            self.primary_ai, self.secondary_ai = self.secondary_ai, self.primary_ai
        
        # 3. 최종 종합
        yield {"stage": "final_synthesis", "status": "종합 중"}
        
        final_prompt = self._create_final_synthesis_prompt()
        final_synthesis = self._call_ai(self.primary_ai, final_prompt)
        
        yield {
            "stage": "final_synthesis",
            "status": "완료",
            "content": final_synthesis,
            "total_rounds": len(self.debate_history)
        }
    
    def run_stock_debate(self, ticker: str, stock_data: Dict, max_rounds: int = 3) -> Generator[Dict, None, None]:
        """
        개별 주식 분석 토론 실행
        
        Args:
            ticker: 주식 티커
            stock_data: 주식 분석 데이터
            max_rounds: 최대 토론 라운드 수
        """
        self.debate_history = []
        
        # 1. 초기 분석
        yield {"stage": "initial_analysis", "ai": self.primary_ai, "status": "시작"}
        
        initial_prompt = self._create_stock_analysis_prompt(ticker, stock_data)
        initial_analysis = self._call_ai(self.primary_ai, initial_prompt)
        
        yield {
            "stage": "initial_analysis",
            "ai": self.primary_ai,
            "status": "완료",
            "content": initial_analysis
        }
        
        current_analysis = initial_analysis
        
        # 2. 토론 라운드
        for round_num in range(1, max_rounds + 1):
            # 비평
            yield {"stage": f"round_{round_num}_critique", "ai": self.secondary_ai, "status": "비평 중"}
            
            critique_prompt = self._create_stock_critique_prompt(ticker, current_analysis, self.primary_ai)
            critique = self._call_ai(self.secondary_ai, critique_prompt)
            
            yield {
                "stage": f"round_{round_num}_critique",
                "ai": self.secondary_ai,
                "status": "완료",
                "content": critique
            }
            
            # 수정
            yield {"stage": f"round_{round_num}_revision", "ai": self.primary_ai, "status": "수정 중"}
            
            revision_prompt = self._create_stock_revision_prompt(ticker, current_analysis, critique, self.secondary_ai)
            revised_analysis = self._call_ai(self.primary_ai, revision_prompt)
            
            yield {
                "stage": f"round_{round_num}_revision",
                "ai": self.primary_ai,
                "status": "완료",
                "content": revised_analysis
            }
            
            # 평가
            yield {"stage": f"round_{round_num}_evaluation", "ai": self.secondary_ai, "status": "평가 중"}
            
            eval_prompt = self._create_evaluation_prompt(revised_analysis)
            evaluation = self._call_ai(self.secondary_ai, eval_prompt)
            agreement_score = self._extract_agreement_score(evaluation)
            
            yield {
                "stage": f"round_{round_num}_evaluation",
                "ai": self.secondary_ai,
                "status": "완료",
                "content": evaluation,
                "agreement_score": agreement_score
            }
            
            # 기록
            debate_round = DebateRound(
                round_num=round_num,
                analyst_ai=self.primary_ai,
                critic_ai=self.secondary_ai,
                analysis=current_analysis,
                critique=critique,
                revised_analysis=revised_analysis,
                agreement_score=agreement_score
            )
            self.debate_history.append(debate_round)
            
            current_analysis = revised_analysis
            
            if agreement_score and agreement_score >= 85:
                yield {"stage": "consensus_reached", "score": agreement_score}
                break
            
            # 역할 교체
            self.primary_ai, self.secondary_ai = self.secondary_ai, self.primary_ai
        
        # 3. 최종 종합
        yield {"stage": "final_synthesis", "status": "종합 중"}
        
        final_prompt = self._create_stock_final_synthesis_prompt(ticker)
        final_synthesis = self._call_ai(self.primary_ai, final_prompt)
        
        yield {
            "stage": "final_synthesis",
            "status": "완료",
            "content": final_synthesis,
            "total_rounds": len(self.debate_history)
        }
    
    # ========== 프롬프트 생성 ==========
    
    def _create_market_analysis_prompt(self, market_data: Dict) -> str:
        """시장 분석 프롬프트"""
        return f"""당신은 전문 시장 분석가입니다. 다음 시장 데이터를 바탕으로 종합적인 시장 분석을 제공해주세요.

## 시장 데이터
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

## 분석 요청사항
1. 현재 시장 상황 진단
2. 핵심 지표 해석 (VIX, 금리, 밸류에이션 등)
3. 리스크 요인과 기회 요인
4. 투자 전략 제안
5. 향후 전망 (단기/중기)

전문적이고 구체적으로 분석해주세요. 한국어로 답변해주세요."""

    def _create_stock_analysis_prompt(self, ticker: str, stock_data: Dict) -> str:
        """주식 분석 프롬프트"""
        return f"""당신은 전문 주식 분석가입니다. {ticker} 종목에 대한 종합적인 분석을 제공해주세요.

## 종목 데이터
{json.dumps(stock_data, indent=2, ensure_ascii=False, default=str)}

## 분석 요청사항
1. 밸류에이션 평가 (PER, PBR, PEG 등)
2. 성장성 및 수익성 분석
3. 기술적 분석 (트렌드, 모멘텀)
4. 리스크 요인
5. 투자 의견 및 목표가 제시

전문적이고 구체적으로 분석해주세요. 한국어로 답변해주세요."""

    def _create_critique_prompt(self, analysis: str, analyst_ai: str) -> str:
        """비평 프롬프트"""
        return f"""당신은 비판적 시각을 가진 시장 전문가입니다. 
다른 분석가({analyst_ai})의 시장 분석을 검토하고 비판적으로 평가해주세요.

## 원본 분석
{analysis}

## 평가 요청사항
1. 분석의 강점 (잘된 부분)
2. 분석의 약점 및 보완 필요 사항
3. 누락된 관점이나 리스크
4. 논리적 오류나 과도한 낙관/비관
5. 구체적인 수정 제안

건설적이고 전문적인 비평을 해주세요. 한국어로 답변해주세요."""

    def _create_stock_critique_prompt(self, ticker: str, analysis: str, analyst_ai: str) -> str:
        """주식 비평 프롬프트"""
        return f"""당신은 비판적 시각을 가진 주식 분석 전문가입니다.
다른 분석가({analyst_ai})의 {ticker} 분석을 검토하고 비판적으로 평가해주세요.

## 원본 분석
{analysis}

## 평가 요청사항
1. 밸류에이션 분석의 적절성
2. 놓친 리스크 요인
3. 과도한 낙관/비관 여부
4. 산업/경쟁 분석의 충분성
5. 구체적인 수정 제안

건설적이고 전문적인 비평을 해주세요. 한국어로 답변해주세요."""

    def _create_revision_prompt(self, original: str, critique: str, critic_ai: str) -> str:
        """수정 프롬프트"""
        return f"""당신은 시장 분석가입니다. 비평가({critic_ai})의 피드백을 반영하여 분석을 수정해주세요.

## 원본 분석
{original}

## 받은 비평
{critique}

## 수정 요청
1. 타당한 비판은 반영하여 분석 수정
2. 동의하지 않는 부분은 논리적으로 반박
3. 누락된 관점 보완
4. 더 균형잡힌 시각 제시

수정된 종합 분석을 제공해주세요. 한국어로 답변해주세요."""

    def _create_stock_revision_prompt(self, ticker: str, original: str, critique: str, critic_ai: str) -> str:
        """주식 수정 프롬프트"""
        return f"""당신은 주식 분석가입니다. 비평가({critic_ai})의 피드백을 반영하여 {ticker} 분석을 수정해주세요.

## 원본 분석
{original}

## 받은 비평
{critique}

## 수정 요청
1. 타당한 비판 반영
2. 동의하지 않는 부분 논리적 반박
3. 누락된 관점 보완
4. 더 정확한 밸류에이션 제시

수정된 종합 분석을 제공해주세요. 한국어로 답변해주세요."""

    def _create_evaluation_prompt(self, revised_analysis: str) -> str:
        """평가 프롬프트"""
        return f"""당신은 분석 품질 평가자입니다. 수정된 분석을 평가해주세요.

## 수정된 분석
{revised_analysis}

## 평가 요청
1. 분석의 완성도 (1-100점)
2. 논리적 일관성
3. 실용성
4. 추가 수정 필요 여부

**중요**: 반드시 아래 형식으로 점수를 포함해주세요:
합의 점수: XX점

한국어로 답변해주세요."""

    def _create_final_synthesis_prompt(self) -> str:
        """최종 종합 프롬프트"""
        history_text = "\n\n".join([
            f"### 라운드 {r.round_num}\n"
            f"**분석가**: {r.analyst_ai}\n"
            f"**비평가**: {r.critic_ai}\n"
            f"**합의 점수**: {r.agreement_score}점\n"
            f"**수정된 분석**:\n{r.revised_analysis[:500]}..."
            for r in self.debate_history
        ])
        
        return f"""당신은 수석 시장 전략가입니다. 
두 AI 분석가의 토론 결과를 종합하여 최종 시장 분석 보고서를 작성해주세요.

## 토론 히스토리
{history_text}

## 최종 보고서 작성
1. 핵심 결론 (두 AI가 합의한 부분)
2. 쟁점 사항 (의견이 갈린 부분과 그 이유)
3. 종합 투자 전략
4. 주의사항 및 리스크

전문적이고 실용적인 최종 보고서를 작성해주세요. 한국어로 답변해주세요."""

    def _create_stock_final_synthesis_prompt(self, ticker: str) -> str:
        """주식 최종 종합 프롬프트"""
        history_text = "\n\n".join([
            f"### 라운드 {r.round_num}\n"
            f"**수정된 분석**:\n{r.revised_analysis[:500]}..."
            for r in self.debate_history
        ])
        
        return f"""당신은 수석 주식 분석가입니다.
두 AI 분석가의 {ticker} 토론 결과를 종합하여 최종 투자 의견을 작성해주세요.

## 토론 히스토리
{history_text}

## 최종 보고서 작성
1. 종합 투자 의견 (매수/보유/매도)
2. 목표가 및 근거
3. 핵심 투자 포인트
4. 주요 리스크
5. 투자 전략

전문적이고 실용적인 최종 보고서를 작성해주세요. 한국어로 답변해주세요."""

    def _extract_agreement_score(self, evaluation: str) -> Optional[float]:
        """평가에서 합의 점수 추출"""
        import re
        
        patterns = [
            r'합의\s*점수[:\s]*(\d+)',
            r'완성도[:\s]*(\d+)',
            r'(\d+)\s*점',
            r'(\d+)/100'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, evaluation)
            if match:
                score = float(match.group(1))
                if 0 <= score <= 100:
                    return score
        
        return 70.0  # 기본값
