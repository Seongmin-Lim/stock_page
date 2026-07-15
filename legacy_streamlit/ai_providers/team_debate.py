"""
🏆 AI 팀 토론 시스템 v4
- Native API 우선 사용 (Anthropic, OpenAI, Gemini)
- GitHub Models API fallback
- Copilot CLI 비활성화
- 다중 팀 지원 (2팀 이상)
- 동적 팀 구성 (사용자가 팀장/팀원 직접 선택)
- QA 평가
- 역할별/직급별 철학 적용
- AI ON/OFF 설정 지원

API 호출 우선순위:
1. Native API (Anthropic Claude, OpenAI GPT, Google Gemini)
2. GitHub Models (gpt-4o, deepseek, llama, phi 등)

비활성화된 기능:
- Copilot CLI (오류 다수로 비활성화)
- Grok (현재 사용 불가)
"""
from typing import Dict, List, Optional, Generator, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import sys
import os
import subprocess
import shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =====================================================
# 🎭 역할별 철학 (Role Philosophies)
# =====================================================
ROLE_PHILOSOPHIES = {
    "analyst": {
        "name": "분석가 (Analyst)",
        "philosophy": """당신은 데이터 중심의 분석가입니다.
- 📊 모든 주장은 반드시 데이터와 수치로 뒷받침해야 합니다
- 🔍 객관적 사실과 주관적 해석을 명확히 구분하세요
- ⚠️ 불확실성과 리스크를 항상 명시하세요
- 📈 트렌드와 패턴을 식별하고 설명하세요""",
    },
    "strategist": {
        "name": "전략가 (Strategist)",
        "philosophy": """당신은 장기적 관점의 전략가입니다.
- 🎯 큰 그림(Big Picture)을 먼저 보고 세부사항으로 내려가세요
- 🌐 거시경제, 지정학적 요소, 산업 트렌드를 고려하세요
- ⚖️ 리스크 대비 수익률(Risk-Reward)을 항상 계산하세요
- 🔮 여러 시나리오를 제시하고 각 확률을 평가하세요""",
    },
    "critic": {
        "name": "비평가 (Critic)",
        "philosophy": """당신은 날카로운 비평가입니다.
- 🔬 논리적 허점과 약점을 찾아내세요
- ❓ 가정(assumption)에 의문을 제기하세요
- 🎯 반대 의견과 대안을 적극적으로 제시하세요
- ⚡ Devil's Advocate 역할을 수행하세요""",
    },
    "synthesizer": {
        "name": "종합가 (Synthesizer)",
        "philosophy": """당신은 정보를 종합하는 전문가입니다.
- 🔗 다양한 관점을 연결하고 통합하세요
- 📋 핵심 포인트를 명확하게 정리하세요
- 🎯 실행 가능한 결론을 도출하세요
- 📝 복잡한 내용을 쉽게 설명하세요""",
    },
    "risk_manager": {
        "name": "리스크 관리자 (Risk Manager)",
        "philosophy": """당신은 리스크 관리 전문가입니다.
- ⚠️ 잠재적 위험 요소를 먼저 식별하세요
- 🛡️ 하방 리스크(Downside Risk) 보호를 최우선으로 하세요
- 📉 최악의 시나리오(Worst Case)를 항상 고려하세요
- 🎚️ 리스크 허용 범위 내에서 판단하세요""",
    },
}

# =====================================================
# 👔 직급별 철학 (Position Philosophies)
# =====================================================
POSITION_PHILOSOPHIES = {
    "leader": {
        "name": "팀장 (Team Leader)",
        "philosophy": """당신은 팀장입니다.
- 👁️ 전체적인 방향성과 품질을 책임집니다
- ✅ 팀원의 분석을 검토하고 승인/반려 권한이 있습니다
- 🎯 최종 결론의 정확성과 설득력을 보장하세요
- 📢 팀을 대표하여 발표하고 다른 팀과 토론합니다
- 💡 팀원에게 건설적인 피드백을 제공하세요""",
    },
    "member": {
        "name": "팀원 (Team Member)",
        "philosophy": """당신은 팀원입니다.
- 📝 초기 분석과 리서치를 담당합니다
- 🔍 데이터를 수집하고 상세하게 분석하세요
- 📊 근거와 출처를 명확히 제시하세요
- 🔄 팀장의 피드백을 반영하여 수정하세요
- 💪 팀장이 승인할 때까지 개선을 반복하세요""",
    },
    "judge": {
        "name": "QA (Quality Assurance)",
        "philosophy": """당신은 품질 보증(QA) 전문가입니다.
- 🔍 모든 팀의 분석 품질을 검증하세요
- ⚖️ 데이터의 정확성과 논리의 일관성을 확인하세요
- 🐛 분석의 오류, 편향, 논리적 허점을 찾아내세요
- ✅ 각 팀 분석의 강점과 약점을 명확히 정리하세요
- 📊 최종적으로 가장 신뢰할 수 있는 결론을 도출하세요
- 🎯 투자자에게 실질적으로 도움이 되는 종합 의견을 제시하세요""",
    },
}


# =====================================================
# � Native API 모델 (최우선 - 자체 API 키)
# Copilot CLI 비활성화, Grok 비활성화
# =====================================================
NATIVE_MODELS = {
    # === Anthropic Claude 계열 ===
    "anthropic": [
        "claude-sonnet-4-20250514",      # 최신 Sonnet 4
        "claude-3-5-sonnet-20241022",    # Claude 3.5 Sonnet
        "claude-3-haiku-20240307",       # Claude 3 Haiku (경량)
    ],
    # === OpenAI GPT 계열 ===
    "openai": [
        "gpt-4-turbo",                   # GPT-4 Turbo
        "gpt-4o",                        # GPT-4o (최신)
        "gpt-4",                         # GPT-4
        "gpt-3.5-turbo",                 # GPT-3.5 Turbo (경량)
    ],
    # === Google Gemini 계열 ===
    "gemini": [
        "gemini-2.0-flash-exp",          # Gemini 2.0 Flash (최신)
        "gemini-1.5-flash",              # Gemini 1.5 Flash
    ],
    # Grok 비활성화 (현재 사용 불가)
    # "grok": ["grok-2", "grok-2-mini"],
}

# Native API 전체 모델 (플랫 리스트) - 계열별 정리
NATIVE_MODELS_FLAT = {
    # === 🧠 Anthropic Claude 계열 ===
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022",
    "claude-3-haiku-20240307": "claude-3-haiku-20240307",
    
    # === 🤖 OpenAI GPT 계열 ===
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4o": "gpt-4o",
    "gpt-4": "gpt-4",
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    
    # === 💎 Google Gemini 계열 ===
    "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
    "gemini-1.5-flash": "gemini-1.5-flash",
}

# Native API 티어별 분류
NATIVE_MODELS_BY_TIER = {
    "premium": [
        # Claude
        "claude-sonnet-4-20250514",
        # GPT
        "gpt-4-turbo", "gpt-4o", "gpt-4",
        # Gemini
        "gemini-2.0-flash-exp",
    ],
    "standard": [
        "claude-3-5-sonnet-20241022",
        "gemini-1.5-flash",
    ],
    "light": [
        "claude-3-haiku-20240307",
        "gpt-3.5-turbo",
    ]
}

# =====================================================
# 🐙 GitHub Models API (두 번째 우선순위)
# 계열별 정리
# =====================================================
GITHUB_MODELS = {
    # === 🤖 OpenAI GPT 계열 ===
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "gpt-4.1-nano": "gpt-4.1-nano",
    
    # === 🔬 DeepSeek 계열 ===
    "deepseek-r1": "DeepSeek-R1",
    "deepseek-r1-0528": "DeepSeek-R1-0528",
    
    # === 🦙 Meta Llama 계열 ===
    "llama-3.3-70b": "Llama-3.3-70B-Instruct",
    "llama-3.2-90b-vision": "Llama-3.2-90B-Vision-Instruct",
    
    # === 🔷 Microsoft Phi 계열 ===
    "phi-4": "Phi-4",
    "phi-4-mini": "Phi-4-mini-instruct",
    
    # === ⚡ Mistral 계열 ===
    "codestral": "Codestral-2501",
}

# GitHub Models 티어별 분류
GITHUB_MODELS_BY_TIER = {
    "premium": [
        # GPT
        "gpt-4o", "gpt-4.1",
        # DeepSeek
        "deepseek-r1", "deepseek-r1-0528",
        # Llama
        "llama-3.3-70b", "llama-3.2-90b-vision",
    ],
    "standard": [
        # Phi
        "phi-4",
        # Mistral
        "codestral",
    ],
    "light": [
        # GPT 경량
        "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano",
        # Phi 경량
        "phi-4-mini",
    ]
}

# =====================================================
# ❌ Copilot CLI 비활성화 (오류 다수)
# =====================================================
COPILOT_MODELS = {}  # 비활성화
COPILOT_MODELS_BY_TIER = {"premium": [], "standard": [], "light": []}

# =====================================================
# 🧠 AI 제공자별 철학/특성
# =====================================================
AI_PROVIDER_PHILOSOPHIES = {
    "anthropic": {
        "name": "Anthropic Claude",
        "icon": "🧠",
        "philosophy": """Claude는 Anthropic이 개발한 AI로, **Constitutional AI** 방식으로 훈련되었습니다.
- 🛡️ **안전성 중시**: 윤리적 판단과 해로운 출력 방지에 특화
- 📚 **정확한 인용**: 불확실한 정보는 명확히 표시
- 🤔 **신중한 분석**: 단정적 표현보다 뉘앙스 있는 분석 선호
- 💭 **긴 문맥 이해**: 200K 토큰까지 처리 가능

투자 분석 시: 리스크 경고를 상세히 하고, 과도한 낙관을 피하는 경향""",
        "style": "신중하고 균형 잡힌 분석",
        "enabled": True,
    },
    "openai": {
        "name": "OpenAI GPT",
        "icon": "🤖",
        "philosophy": """GPT는 OpenAI가 개발한 범용 AI 모델입니다.
- 🎨 **창의성**: 다양한 관점과 아이디어 생성에 강점
- 📊 **범용성**: 코딩, 분석, 창작 등 다방면에 우수
- 🔄 **적응력**: 사용자 스타일에 맞춰 응답 조절
- 🧮 **추론력**: 복잡한 논리적 추론 능력

투자 분석 시: 다양한 시나리오를 창의적으로 제시하고, 실행 가능한 전략 도출""",
        "style": "창의적이고 실용적인 분석",
        "enabled": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "icon": "💎",
        "philosophy": """Gemini는 Google DeepMind가 개발한 멀티모달 AI입니다.
- 🌐 **실시간 정보**: Google 검색 연동으로 최신 정보 접근
- 📈 **데이터 분석**: 숫자/차트 분석에 강점
- 🖼️ **멀티모달**: 텍스트, 이미지, 코드 통합 처리
- 🔬 **과학적 접근**: 근거 기반의 체계적 분석

투자 분석 시: 데이터 중심의 정량적 분석, 최신 시장 동향 반영""",
        "style": "데이터 중심의 정량적 분석",
        "enabled": True,
    },
    "github": {
        "name": "GitHub Models",
        "icon": "🐙",
        "philosophy": """GitHub Models는 다양한 오픈소스 및 상용 모델을 제공합니다.
- 🔬 **DeepSeek**: 깊은 추론 능력, 복잡한 문제 해결
- 🦙 **Llama**: Meta의 오픈소스 모델, 균형 잡힌 성능
- 🔷 **Phi**: Microsoft의 경량 모델, 빠른 응답
- ⚡ **Codestral**: Mistral의 코딩 특화 모델

투자 분석 시: 다양한 관점의 분석, 비용 효율적""",
        "style": "다양한 관점의 분석",
        "enabled": True,
    },
}

# =====================================================
# 📦 전체 모델 통합 (Native + GitHub)
# Copilot CLI 제외
# =====================================================
ALL_AVAILABLE_MODELS = {**NATIVE_MODELS_FLAT, **GITHUB_MODELS}

# 중복 제거된 티어 목록
def _unique_list(lst):
    """리스트 중복 제거 (순서 유지)"""
    seen = set()
    return [x for x in lst if not (x in seen or seen.add(x))]

ALL_MODELS_BY_TIER = {
    "premium": _unique_list(
        NATIVE_MODELS_BY_TIER["premium"] + 
        GITHUB_MODELS_BY_TIER["premium"]
    ),
    "standard": _unique_list(
        NATIVE_MODELS_BY_TIER["standard"] + 
        GITHUB_MODELS_BY_TIER["standard"]
    ),
    "light": _unique_list(
        NATIVE_MODELS_BY_TIER["light"] + 
        GITHUB_MODELS_BY_TIER["light"]
    ),
}

# 계열별 모델 분류 (UI용)
MODELS_BY_FAMILY = {
    "claude": {
        "name": "🧠 Anthropic Claude",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "source": "native",
    },
    "gpt": {
        "name": "🤖 OpenAI GPT",
        "models": ["gpt-4-turbo", "gpt-4o", "gpt-4", "gpt-3.5-turbo", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
        "source": "mixed",  # Native + GitHub
    },
    "gemini": {
        "name": "💎 Google Gemini",
        "models": ["gemini-2.0-flash-exp", "gemini-1.5-flash"],
        "source": "native",
    },
    "deepseek": {
        "name": "🔬 DeepSeek",
        "models": ["deepseek-r1", "deepseek-r1-0528"],
        "source": "github",
    },
    "llama": {
        "name": "🦙 Meta Llama",
        "models": ["llama-3.3-70b", "llama-3.2-90b-vision"],
        "source": "github",
    },
    "phi": {
        "name": "🔷 Microsoft Phi",
        "models": ["phi-4", "phi-4-mini"],
        "source": "github",
    },
    "mistral": {
        "name": "⚡ Mistral",
        "models": ["codestral"],
        "source": "github",
    },
}

# 모델 → 소스 매핑
def get_model_source(model: str) -> str:
    """모델의 소스(GitHub/Native) 반환"""
    if model in NATIVE_MODELS_FLAT:
        return "native"
    elif model in GITHUB_MODELS:
        return "github"
    return "unknown"

def get_model_provider(model: str) -> str:
    """Native API 모델의 제공자 반환"""
    for provider, models in NATIVE_MODELS.items():
        if model in models:
            return provider
    return None

def get_model_family(model: str) -> str:
    """모델의 계열 반환 (claude, gpt, gemini 등)"""
    for family, info in MODELS_BY_FAMILY.items():
        if model in info["models"]:
            return family
    return "unknown"


@dataclass
class TeamConfig:
    """팀 구성 (5인 1팀: 팀장 + 역할별 팀원 4명)"""
    name: str
    leader_model: str  # 팀장 (종합가)
    member_model: str = None  # 단일 팀원 모델 (간편 모드용)
    # 역할별 팀원 (확장 모드)
    analyst_model: str = None      # 분석가
    strategist_model: str = None   # 전략가
    critic_model: str = None       # 비평가
    risk_manager_model: str = None # 리스크 관리자
    color: str = "blue"
    use_extended_team: bool = False  # True: 5인팀, False: 2인팀
    
    def get_members(self) -> Dict[str, str]:
        """팀원 역할-모델 매핑 반환"""
        if self.use_extended_team:
            return {
                "analyst": self.analyst_model,
                "strategist": self.strategist_model,
                "critic": self.critic_model,
                "risk_manager": self.risk_manager_model,
            }
        else:
            # 간편 모드: 단일 팀원이 모든 역할 수행
            return {"analyst": self.member_model}
    
    def get_active_roles(self) -> List[str]:
        """활성화된 역할 목록"""
        if self.use_extended_team:
            return ["analyst", "strategist", "critic", "risk_manager"]
        return ["analyst"]


@dataclass 
class TeamWork:
    """팀 작업 결과"""
    team_name: str
    member_draft: str  # 간편 모드용 (또는 통합 초안)
    leader_review: str
    revision_count: int
    final_analysis: str
    approved: bool = False
    score: int = 0  # 팀장 평가 점수 (1-10)
    # 확장 모드: 역할별 분석 결과
    role_analyses: Dict[str, str] = field(default_factory=dict)


@dataclass
class MultiTeamDebateResult:
    """다중 팀 토론 결과"""
    team_arguments: Dict[str, str] = field(default_factory=dict)
    team_rebuttals: Dict[str, str] = field(default_factory=dict)
    qa_evaluation: str = ""
    rankings: List[str] = field(default_factory=list)


# =====================================================
# ❌ Copilot CLI 비활성화 (오류 다수로 인해 비활성화)
# =====================================================
class CopilotCLIClient:
    """Copilot CLI 클라이언트 (비활성화됨)"""
    
    def __init__(self):
        # 비활성화됨
        pass
    
    def is_available(self) -> bool:
        return False  # 항상 False
    
    def call(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        return None  # 항상 None


class GitHubModelsClient:
    """GitHub Models 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
        self.client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://models.github.ai/inference"
                )
                print("✅ GitHub Models 클라이언트 초기화 성공")
            except Exception as e:
                print(f"⚠️ GitHub Models 초기화 실패: {e}")
        else:
            print("⚠️ GITHUB_TOKEN 미설정")
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def call(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.client:
            return None
        
        actual_model = GITHUB_MODELS.get(model, model)
        
        try:
            response = self.client.chat.completions.create(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ GitHub Models ({model}) 호출 실패: {e}")
            return None


class NativeAPIClient:
    """자체 API 클라이언트 (Anthropic, OpenAI, Gemini)"""
    
    def __init__(self):
        self.clients = {}
        self._init_clients()
    
    def _init_clients(self):
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and not openai_key.startswith("your_"):
            try:
                from openai import OpenAI
                self.clients["openai"] = OpenAI(api_key=openai_key)
                print("✅ OpenAI API 사용 가능")
            except: pass
        
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and not anthropic_key.startswith("your_"):
            try:
                import anthropic
                self.clients["anthropic"] = anthropic.Anthropic(api_key=anthropic_key)
                print("✅ Anthropic API 사용 가능")
            except: pass
        
        # Gemini
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if google_key and not google_key.startswith("your_"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_key)
                self.clients["gemini"] = genai
                print("✅ Gemini API 사용 가능")
            except: pass
        
        # Grok 비활성화 (현재 사용 불가)
        # grok_key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
        # if grok_key and not grok_key.startswith("your_"):
        #     ...
    
    def get_provider_for_model(self, model: str) -> Optional[str]:
        for provider, models in NATIVE_MODELS.items():
            if model in models or any(m in model for m in models):
                if provider in self.clients:
                    return provider
        return None
    
    def call(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        provider = self.get_provider_for_model(model)
        if not provider:
            return None
        
        client = self.clients.get(provider)
        if not client:
            return None
        
        try:
            if provider == "openai":
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.7, max_tokens=4000
                )
                return resp.choices[0].message.content
            
            elif provider == "anthropic":
                resp = client.messages.create(
                    model=model, max_tokens=4000, system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                return resp.content[0].text
            
            elif provider == "gemini":
                # 올바른 모델명 사용
                gemini_model_map = {
                    "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
                    "gemini-1.5-flash": "gemini-1.5-flash",
                }
                actual_model = gemini_model_map.get(model, "gemini-2.0-flash-exp")
                m = client.GenerativeModel(actual_model)
                resp = m.generate_content(f"{system_prompt}\n\n{user_prompt}")
                return resp.text
            
        except Exception as e:
            print(f"⚠️ {provider} API ({model}) 실패: {e}")
        return None


class AITeamDebateSystem:
    """
    다중 팀 AI 토론 시스템 v2
    
    토론 플로우:
    ============
    [Phase 1: 팀 내부 작업] - 각 팀이 병렬적으로 내부 작업 수행
        1. 팀원이 초안 분석 작성
        2. 팀장이 검토 및 피드백
        3. 팀원이 수정 (필요시 반복)
        4. 팀장이 최종 승인 → "제출 준비 완료"
    
    [Phase 2: 팀별 발표] - 모든 팀이 승인 후 순차적으로 발표
        1. 각 팀장이 팀의 분석 결과를 정리하여 발표
        2. 다른 팀들은 발표 내용 청취
    
    [Phase 3: 팀간 토론] - 서로의 발표를 기반으로 토론
        1. 각 팀이 자신의 강점 주장
        2. 상대 팀 분석의 약점 지적 (반박)
        3. 최종 방어
    
    [Phase 4: QA 평가] - QA가 최종 평가
        1. 모든 분석, 발표, 토론 내용 종합
        2. 점수 및 순위 부여
        3. 최종 투자 권고 생성
    
    prefer_native 옵션:
        - True: Native API 우선 (버튼 클릭 수동 분석 시)
        - False: GitHub Models 우선 (초기 로딩 자동 분석 시)
    """
    
    def __init__(self, teams: List[TeamConfig], qa_model: str = "gpt-4o", prefer_native: bool = True):
        """
        Args:
            teams: 토론에 참여할 팀 설정 리스트
            qa_model: QA 평가에 사용할 모델
            prefer_native: True=Native API 우선(수동), False=GitHub 우선(자동)
        """
        self.teams = teams
        self.qa_model = qa_model
        self.prefer_native = prefer_native  # Native vs GitHub 우선순위
        self.github_client = GitHubModelsClient()
        self.native_client = NativeAPIClient()
        self.available_teams = []
        self.unavailable_info = []
        self._check_team_availability()
    
    def _check_team_availability(self):
        for team in self.teams:
            leader_ok = self._check_model(team.leader_model, f"{team.name} 팀장")
            member_ok = self._check_model(team.member_model, f"{team.name} 팀원")
            
            if leader_ok and member_ok:
                self.available_teams.append(team)
                print(f"✅ {team.name} 참가 가능")
            else:
                missing = []
                if not leader_ok: missing.append(f"팀장({team.leader_model})")
                if not member_ok: missing.append(f"팀원({team.member_model})")
                self.unavailable_info.append(f"{team.name}: {', '.join(missing)}")
                print(f"❌ {team.name} 참가 불가 - 해당 AI는 참가하지 않았음: {', '.join(missing)}")
    
    def _check_model(self, model: str, role: str) -> bool:
        """모델 사용 가능 여부 확인 (Native → GitHub 순서)"""
        
        # 1. Native API (최우선)
        if model in NATIVE_MODELS_FLAT:
            provider = self.native_client.get_provider_for_model(model)
            if provider:
                print(f"  ✓ {role}: 🔑 Native API ({model}) - {provider}")
                return True
        
        # 2. GitHub Models
        if self.github_client.is_available() and model in GITHUB_MODELS:
            print(f"  ✓ {role}: 🐙 GitHub Models ({model})")
            return True
        
        # 3. Fallback 가능 여부 확인
        # Native API 키가 있으면 fallback 가능
        if self.native_client.clients:
            print(f"  ⚡ {role}: {model} → Native API fallback 가능")
            return True
        
        # GitHub Models가 가능하면 fallback 가능
        if self.github_client.is_available():
            print(f"  ⚡ {role}: {model} → GitHub Models fallback 가능")
            return True
        
        print(f"  ✗ {role}: {model} - 해당 AI는 사용 불가")
        return False
    
    def _call_ai(self, model: str, system_prompt: str, user_prompt: str, prefer_native: bool = None) -> str:
        """
        AI 호출
        
        Args:
            model: 사용할 모델명
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            prefer_native: True면 Native API 우선, False면 GitHub Models 우선
                           None이면 self.prefer_native 사용
        """
        # prefer_native가 None이면 인스턴스 설정값 사용
        if prefer_native is None:
            prefer_native = self.prefer_native
        
        source = get_model_source(model)
        
        if prefer_native:
            # Native API 우선 (버튼 클릭 시)
            result = self._try_native_first(model, system_prompt, user_prompt)
            if result:
                return result
            
            # GitHub Models fallback
            result = self._try_github_models(model, system_prompt, user_prompt)
            if result:
                return result
        else:
            # GitHub Models 우선 (초기 로딩 시)
            result = self._try_github_models(model, system_prompt, user_prompt)
            if result:
                return result
            
            # Native API fallback
            result = self._try_native_first(model, system_prompt, user_prompt)
            if result:
                return result
        
        return f"[{model} 사용 불가 - 모든 소스 실패]"
    
    def _try_native_first(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Native API 시도 (매핑 포함)"""
        source = get_model_source(model)
        
        # 직접 호출 시도
        if source == "native" or model in NATIVE_MODELS_FLAT:
            result = self.native_client.call(model, system_prompt, user_prompt)
            if result:
                print(f"✅ 🔑 Native API ({model}) 응답")
                return result
            print(f"⚠️ Native API ({model}) 실패, fallback...")
        
        # 모델 매핑으로 fallback
        if self.native_client.clients:
            native_mapping = {
                # GitHub gpt → Native gpt
                "gpt-4o": "gpt-4o",
                "gpt-4o-mini": "gpt-3.5-turbo",
                "gpt-4.1": "gpt-4-turbo",
                "gpt-4.1-mini": "gpt-3.5-turbo",
                # DeepSeek → Native GPT
                "deepseek-r1": "gpt-4-turbo",
                "deepseek-r1-0528": "gpt-4-turbo",
                # Llama → Native Claude
                "llama-3.3-70b": "claude-sonnet-4-20250514",
                "llama-3.2-90b-vision": "claude-3-5-sonnet-20241022",
                # Phi → Native Gemini
                "phi-4": "gemini-2.0-flash-exp",
                "phi-4-mini": "gemini-1.5-flash",
                # Mistral → Native GPT
                "codestral": "gpt-4-turbo",
            }
            
            native_model = native_mapping.get(model)
            if native_model:
                result = self.native_client.call(native_model, system_prompt, user_prompt)
                if result:
                    print(f"✅ 🔑 Native API fallback ({model} → {native_model}) 응답")
                    return result
        
        return None
    
    def _try_github_models(self, model: str, system_prompt: str, user_prompt: str) -> Optional[str]:
        """GitHub Models 시도 (매핑 포함)"""
        if not self.github_client.is_available():
            return None
        
        # 직접 호출 시도
        if model in GITHUB_MODELS:
            result = self.github_client.call(model, system_prompt, user_prompt)
            if result:
                print(f"✅ 🐙 GitHub Models ({model}) 응답")
                return result
            print(f"⚠️ GitHub Models ({model}) 실패, fallback...")
        
        # 모델 매핑으로 fallback
        github_mapping = {
            # Native Claude → GitHub gpt-4o
            "claude-sonnet-4-20250514": "gpt-4o",
            "claude-3-5-sonnet-20241022": "gpt-4o",
            "claude-3-haiku-20240307": "gpt-4o-mini",
            # Native GPT → GitHub gpt
            "gpt-4-turbo": "gpt-4o",
            "gpt-4": "gpt-4o",
            "gpt-4o": "gpt-4o",  # 같은 모델
            "gpt-3.5-turbo": "gpt-4o-mini",
            # Native Gemini → GitHub phi-4
            "gemini-2.0-flash-exp": "phi-4",
            "gemini-1.5-flash": "phi-4-mini",
        }
        
        github_model = github_mapping.get(model)
        if github_model:
            result = self.github_client.call(github_model, system_prompt, user_prompt)
            if result:
                print(f"✅ 🐙 GitHub Models ({model} → {github_model}) 응답")
                return result
        
        # 기본 fallback: gpt-4o
        result = self.github_client.call("gpt-4o", system_prompt, user_prompt)
        if result:
            print(f"✅ 🐙 GitHub Models ({model} → gpt-4o) 응답 (기본 fallback)")
            return result
        
        return None
    
    # =========================================================
    # Phase 1: 팀 내부 작업 (역할별 분석 → 팀장 종합)
    # =========================================================
    def _team_internal_work(self, team: TeamConfig, idx: int, market_data: Dict, task: str, max_rev: int = 2):
        """팀 내부 작업: 역할별 팀원이 분석하고 팀장이 종합"""
        
        yield {"stage": "team_internal_start", "team": team.name, "team_idx": idx, "phase": "internal", 
               "message": f"📋 [{team.name}] 내부 작업 시작 ({'5인 팀' if team.use_extended_team else '2인 팀'})"}
        
        # 확장 모드 (5인 팀) vs 간편 모드 (2인 팀)
        if team.use_extended_team:
            yield from self._extended_team_work(team, idx, market_data, task, max_rev)
        else:
            yield from self._simple_team_work(team, idx, market_data, task, max_rev)
    
    def _extended_team_work(self, team: TeamConfig, idx: int, market_data: Dict, task: str, max_rev: int = 2):
        """5인 팀 작업: 역할별 분석 → 팀장 종합"""
        
        members = team.get_members()
        role_analyses = {}
        
        # Step 1: 각 역할별 팀원이 전문 분석 수행
        yield {"stage": "roles_analyzing", "team": team.name, "team_idx": idx, 
               "roles": list(members.keys()), "message": f"🔍 [{team.name}] 역할별 전문 분석 시작 ({len(members)}명)"}
        
        for role, model in members.items():
            if not model:
                continue
            
            role_info = ROLE_PHILOSOPHIES.get(role, {})
            role_name = role_info.get("name", role)
            role_philosophy = role_info.get("philosophy", "")
            
            yield {"stage": f"role_{role}_analyzing", "team": team.name, "team_idx": idx, 
                   "role": role, "model": model, "message": f"🔍 [{team.name}] {role_name}({model}) 분석 중..."}
            
            # 역할별 특화된 프롬프트
            role_prompts = {
                "analyst": f"""분석 과제: {task}

시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

**분석가 관점**에서 다음을 분석하세요:
1. 📊 핵심 데이터 분석 (수치, 트렌드, 패턴)
2. 📈 기술적 지표 해석 (RSI, MACD, 이동평균 등)
3. 📉 밸류에이션 분석 (PER, PBR, 성장률)
4. 🔢 정량적 투자 판단 기준

데이터와 수치에 기반한 객관적 분석을 제공하세요.""",

                "strategist": f"""분석 과제: {task}

시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

**전략가 관점**에서 다음을 분석하세요:
1. 🌐 거시경제 환경 분석 (금리, 인플레이션, 경기 사이클)
2. 🎯 중장기 투자 전략 제안
3. 📊 섹터/자산 배분 전략
4. 🔮 3~6개월 후 시나리오별 전망

큰 그림을 보고 전략적 방향을 제시하세요.""",

                "critic": f"""분석 과제: {task}

시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

**비평가 관점**에서 다음을 분석하세요:
1. ❓ 현재 시장 컨센서스의 허점
2. 🔬 숨겨진 리스크와 블랙스완 가능성
3. 🎭 역발상(Contrarian) 관점
4. ⚠️ 낙관론에 대한 반박 논거

Devil's Advocate 역할로 비판적 시각을 제공하세요.""",

                "risk_manager": f"""분석 과제: {task}

시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

**리스크 관리자 관점**에서 다음을 분석하세요:
1. ⚠️ 주요 리스크 요인 식별 (시장, 신용, 유동성, 지정학)
2. 📉 최악의 시나리오(Worst Case) 분석
3. 🛡️ 헤지 전략 및 포지션 관리
4. 🎚️ 적정 현금 비중 및 손절 기준

하방 리스크 보호를 최우선으로 분석하세요."""
            }
            
            analysis = self._call_ai(
                model,
                f"""당신은 {team.name}의 {role_name}입니다.
{role_philosophy}

팀장에게 보고할 전문 분석을 작성하세요.""",
                role_prompts.get(role, f"분석 과제: {task}\n시장 데이터: {json.dumps(market_data, default=str)}")
            )
            
            role_analyses[role] = analysis
            
            yield {"stage": f"role_{role}_done", "team": team.name, "team_idx": idx, 
                   "role": role, "content": analysis, "message": f"✅ [{team.name}] {role_name} 분석 완료"}
        
        # Step 2: 팀장이 역할별 분석을 종합
        yield {"stage": "leader_synthesizing", "team": team.name, "team_idx": idx, 
               "model": team.leader_model, "message": f"👔 [{team.name}] 팀장({team.leader_model})이 종합 분석 중..."}
        
        # 역할별 분석 요약 생성
        roles_summary = "\n\n".join([
            f"=== [{ROLE_PHILOSOPHIES.get(role, {}).get('name', role)}] 분석 ===\n{analysis[:800]}..."
            for role, analysis in role_analyses.items()
        ])
        
        synthesized_analysis = self._call_ai(
            team.leader_model,
            f"""당신은 {team.name}의 팀장(종합가)입니다.
{POSITION_PHILOSOPHIES['leader']['philosophy']}

{ROLE_PHILOSOPHIES['synthesizer']['philosophy']}

4명의 전문가 분석을 종합하여 최종 팀 의견을 도출하세요.""",
            f"""분석 과제: {task}

시장 데이터 요약:
{json.dumps({k: str(v)[:100] for k, v in market_data.items()}, ensure_ascii=False)}

=== 팀원들의 역할별 전문 분석 ===
{roles_summary}

위 4명의 전문가 분석을 종합하여 다음 형식으로 **팀 최종 분석 보고서**를 작성하세요:

## 1. 종합 시장 판단
(각 전문가 의견의 공통점과 차이점 정리)

## 2. 핵심 투자 전략
- 시장 심리 점수: 0-100
- 투자 시그널: 극도의 공포/공포/중립/탐욕/극도의 탐욕
- 전략 방향: (공격적/중립/방어적)

## 3. 추천 포트폴리오
| 종목/ETF | 비중(%) | 근거 | 담당 분석가 의견 |
|---------|--------|------|---------------|

## 4. 리스크 관리 계획
- 주요 리스크: (리스크 관리자 의견 반영)
- 손절 기준:
- 헤지 전략:

## 5. 팀장 최종 의견
(모든 분석을 종합한 최종 투자 권고)
"""
        )
        
        yield {"stage": "member_draft_done", "team": team.name, "team_idx": idx, 
               "content": synthesized_analysis, "role_analyses": role_analyses,
               "message": f"📝 [{team.name}] 팀장 종합 분석 완료"}
        
        # Step 3: 팀장 자체 검토 (품질 확인)
        yield {"stage": "leader_reviewing", "team": team.name, "team_idx": idx, 
               "model": team.leader_model, "message": f"👔 [{team.name}] 팀장 품질 검토 중..."}
        
        quality_check = self._call_ai(
            team.leader_model,
            f"""당신은 {team.name}의 팀장입니다. 방금 작성한 종합 분석의 품질을 자체 검토하세요.""",
            f"""종합 분석 보고서:
{synthesized_analysis}

다음 JSON 형식으로 자체 평가하세요:
{{
    "approved": true,
    "score": 1-10 점수,
    "strengths": ["장점1", "장점2"],
    "improvements": ["향후 개선점1", "향후 개선점2"],
    "confidence": "높음/중간/낮음"
}}"""
        )
        
        # 점수 파싱
        try:
            import re
            json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', quality_check, re.DOTALL)
            if json_match:
                review_data = json.loads(json_match.group())
                final_score = review_data.get("score", 8)
            else:
                final_score = 8
        except:
            final_score = 8
        
        yield {"stage": "leader_decision", "team": team.name, "team_idx": idx, 
               "approved": True, "score": final_score, "content": quality_check,
               "message": f"✅ 팀 분석 완료! (자체 평가: {final_score}/10)"}
        
        yield {"stage": "team_internal_complete", "team": team.name, "team_idx": idx,
               "approved": True, "score": final_score, "revisions": 0,
               "final_analysis": synthesized_analysis, 
               "role_analyses": role_analyses,
               "message": f"🏁 [{team.name}] 내부 작업 완료 (5인 팀, 점수 {final_score}/10)"}
    
    def _simple_team_work(self, team: TeamConfig, idx: int, market_data: Dict, task: str, max_rev: int = 2):
        """2인 팀 작업: 기존 방식 (팀원 분석 → 팀장 검토 → 수정 루프)"""
        
        # Step 1: 팀원 초안 분석
        yield {"stage": "member_analyzing", "team": team.name, "team_idx": idx, "model": team.member_model, "message": f"🔍 [{team.name}] 팀원({team.member_model})이 초안 분석 중..."}
        
        member_draft = self._call_ai(
            team.member_model,
            f"""당신은 {team.name}의 전문 금융 분석가(팀원)입니다.
팀장의 승인을 받기 위해 최선을 다해 분석해야 합니다.
철저한 데이터 분석, 논리적 근거, 명확한 투자 권고를 포함하세요.""",
            f"""분석 과제: {task}

시장 데이터:
{json.dumps(market_data, indent=2, ensure_ascii=False, default=str)}

다음 형식으로 분석 보고서를 작성하세요:
1. 시장 현황 분석
2. 핵심 지표 해석
3. 리스크 요인
4. 투자 전략 제안
5. 구체적 종목/ETF 추천 (근거 포함)

한국어로 상세히 분석하세요."""
        )
        
        yield {"stage": "member_draft_done", "team": team.name, "team_idx": idx, "content": member_draft, "message": f"📝 [{team.name}] 팀원 초안 완료"}
        
        current_analysis = member_draft
        revision_history = [{"version": 0, "content": member_draft, "type": "initial_draft"}]
        approved = False
        final_score = 0
        
        # Step 2: 팀장 검토/승인 루프
        for rev_round in range(max_rev + 1):
            yield {"stage": "leader_reviewing", "team": team.name, "team_idx": idx, "model": team.leader_model, 
                   "revision_round": rev_round, "message": f"👔 [{team.name}] 팀장({team.leader_model}) 검토 #{rev_round+1}"}
            
            leader_review = self._call_ai(
                team.leader_model,
                f"""당신은 {team.name}의 팀장입니다.
팀원의 분석 보고서를 엄격하지만 공정하게 검토합니다.
품질이 충분하면 승인하고, 부족하면 구체적인 피드백으로 수정을 요청합니다.
승인 기준: 논리적 일관성, 데이터 기반 분석, 실행 가능한 권고안""",
                f"""팀원의 분석 보고서 (v{rev_round+1}):
{current_analysis}

다음 JSON 형식으로 응답하세요:
{{
    "approved": true 또는 false,
    "score": 1-10 점수,
    "strengths": ["장점1", "장점2"],
    "weaknesses": ["약점1", "약점2"],
    "feedback": "구체적인 수정 요청 (미승인 시)",
    "approval_reason": "승인 이유 (승인 시)"
}}"""
            )
            
            # JSON 파싱
            try:
                import re
                json_match = re.search(r'\{[^{}]*"approved"[^{}]*\}', leader_review, re.DOTALL)
                if json_match:
                    review_data = json.loads(json_match.group())
                else:
                    # JSON을 찾지 못하면 텍스트에서 추론
                    review_data = {
                        "approved": "승인" in leader_review or "approved" in leader_review.lower(),
                        "score": 7,
                        "feedback": leader_review
                    }
            except:
                review_data = {"approved": rev_round >= max_rev, "score": 7, "feedback": leader_review}
            
            approved = review_data.get("approved", False)
            final_score = review_data.get("score", 7)
            
            yield {"stage": "leader_decision", "team": team.name, "team_idx": idx, 
                   "approved": approved, "score": final_score, "content": leader_review,
                   "message": f"{'✅ 승인!' if approved else '📝 수정 요청'} (점수: {final_score}/10)"}
            
            revision_history.append({
                "version": rev_round + 1, 
                "type": "leader_review",
                "approved": approved, 
                "score": final_score,
                "content": leader_review
            })
            
            if approved:
                yield {"stage": "team_approved", "team": team.name, "team_idx": idx, 
                       "message": f"🎉 [{team.name}] 팀장 승인 완료! 발표 준비 완료"}
                break
            
            if rev_round >= max_rev:
                yield {"stage": "team_force_submit", "team": team.name, "team_idx": idx,
                       "message": f"⏰ [{team.name}] 수정 한도 도달, 현재 버전으로 제출"}
                break
            
            # Step 3: 팀원 수정
            yield {"stage": "member_revising", "team": team.name, "team_idx": idx, 
                   "revision": rev_round+1, "message": f"✏️ [{team.name}] 팀원이 피드백 반영 중 (수정 #{rev_round+1})"}
            
            revised_analysis = self._call_ai(
                team.member_model,
                f"""당신은 {team.name}의 팀원입니다.
팀장의 피드백을 진지하게 받아들이고 분석을 개선해야 합니다.
지적받은 약점을 보완하고 강점은 유지하세요.""",
                f"""기존 분석:
{current_analysis}

팀장 피드백:
{leader_review}

피드백을 반영하여 개선된 분석 보고서를 작성하세요.
특히 지적받은 부분을 중점적으로 수정하세요."""
            )
            
            current_analysis = revised_analysis
            revision_history.append({"version": rev_round + 1, "type": "revision", "content": revised_analysis})
            
            yield {"stage": "member_revised", "team": team.name, "team_idx": idx, 
                   "content": revised_analysis, "message": f"📄 [{team.name}] 수정본 #{rev_round+1} 완료"}
        
        yield {"stage": "team_internal_complete", "team": team.name, "team_idx": idx,
               "approved": approved, "score": final_score, "revisions": len([r for r in revision_history if r.get("type") == "revision"]),
               "final_analysis": current_analysis, "revision_history": revision_history,
               "message": f"🏁 [{team.name}] 내부 작업 완료 (수정 {len([r for r in revision_history if r.get('type') == 'revision'])}회, 점수 {final_score}/10)"}
    
    # =========================================================
    # Phase 2: 팀별 발표 (팀장이 팀 분석을 정리하여 발표)
    # =========================================================
    def _team_presentation(self, team: TeamConfig, idx: int, final_analysis: str, other_summaries: List[str] = None):
        """팀장이 최종 분석을 정리하여 발표"""
        
        yield {"stage": "presentation_start", "team": team.name, "team_idx": idx, 
               "message": f"🎤 [{team.name}] 발표 준비 중..."}
        
        other_context = ""
        if other_summaries:
            other_context = f"\n\n다른 팀들의 발표 요약 (참고용):\n" + "\n".join(other_summaries)
        
        presentation = self._call_ai(
            team.leader_model,
            f"""당신은 {team.name}의 팀장입니다.
팀의 분석 결과를 청중에게 발표합니다.
핵심 포인트를 명확하게 전달하고, 팀의 분석이 왜 신뢰할 만한지 설득력 있게 설명하세요.""",
            f"""팀 분석 보고서:
{final_analysis}
{other_context}

다음 형식으로 발표를 준비하세요:
1. 🎯 핵심 결론 (30초 요약)
2. 📊 주요 발견 사항 (3-5개 핵심 포인트)
3. 💡 우리 팀만의 차별화된 인사이트
4. 📈 구체적 투자 권고
5. ⚠️ 주요 리스크와 대응 방안

청중을 설득하는 발표 형식으로 작성하세요."""
        )
        
        yield {"stage": "presentation_done", "team": team.name, "team_idx": idx, 
               "content": presentation, "message": f"✅ [{team.name}] 발표 완료!"}
        
        return presentation
    
    # =========================================================
    # Phase 3: 상호 검토 (직장 피드백 스타일)
    # =========================================================
    def _cross_review(self, works: List[TeamWork], presentations: Dict[str, str]):
        """
        상호 검토: 각 팀이 다른 팀의 분석을 검토하고 개선점 제안
        - 직장 피드백 스타일: "이 부분 보완해라" 식의 건설적 피드백
        """
        
        yield {"stage": "cross_review_start", "message": f"🔍 상호 검토 시작! ({len(works)}팀 참가)"}
        
        feedbacks = {}  # 각 팀이 받은 피드백 {team_name: [피드백1, 피드백2, ...]}
        reviews = {}    # 각 팀이 작성한 리뷰 {reviewer: {target: review}}
        
        # 초기화
        for tw in works:
            feedbacks[tw.team_name] = []
        
        # Step 1: 각 팀이 다른 팀들의 분석을 검토하고 피드백 작성
        yield {"stage": "review_phase", "message": "📋 Round 1: 상호 검토 (건설적 피드백)"}
        
        for i, reviewer_tw in enumerate(works):
            reviewer_team = self.available_teams[i]
            reviews[reviewer_tw.team_name] = {}
            
            for j, target_tw in enumerate(works):
                if reviewer_tw.team_name == target_tw.team_name:
                    continue
                
                yield {"stage": "reviewing", "reviewer": reviewer_tw.team_name, "target": target_tw.team_name,
                       "message": f"👀 [{reviewer_tw.team_name}]이(가) [{target_tw.team_name}] 분석 검토 중..."}
                
                review = self._call_ai(
                    reviewer_team.leader_model,
                    f"""당신은 {reviewer_tw.team_name} 팀장입니다. 
다른 팀의 분석을 검토하고 **건설적인 피드백**을 제공해야 합니다.
공격이나 비판이 아니라, 동료의 업무를 더 좋게 만들어주는 피드백을 작성하세요.
직장에서 동료 팀에게 주는 피드백처럼 구체적이고 실행 가능한 조언을 하세요.""",
                    f"""[{target_tw.team_name}]의 분석 보고서:
{presentations.get(target_tw.team_name, target_tw.final_analysis)[:1000]}

다음 형식으로 건설적인 피드백을 작성하세요:

## 👍 잘한 점 (2-3가지)
- 구체적으로 어떤 부분이 좋았는지

## 🔧 보완이 필요한 점 (2-3가지)
- 무엇을: 구체적으로 어떤 부분이 부족한지
- 왜: 왜 보완이 필요한지
- 어떻게: 어떻게 개선하면 좋을지 (구체적 제안)

## 💡 추가 제안
- 놓친 관점이나 고려하면 좋을 요소

반드시 건설적이고 실행 가능한 피드백을 작성하세요."""
                )
                
                reviews[reviewer_tw.team_name][target_tw.team_name] = review
                feedbacks[target_tw.team_name].append({
                    "from": reviewer_tw.team_name,
                    "content": review
                })
                
                yield {"stage": "review_done", "reviewer": reviewer_tw.team_name, "target": target_tw.team_name,
                       "content": review, "message": f"✅ [{reviewer_tw.team_name}] → [{target_tw.team_name}] 피드백 완료"}
        
        yield {"stage": "cross_review_complete", "message": "🏁 상호 검토 완료!",
               "feedbacks": feedbacks, "reviews": reviews}
        
        return feedbacks, reviews
    
    # =========================================================
    # Phase 4: 피드백 기반 분석 강화 (2차 라운드)
    # =========================================================
    def _enhance_analysis(self, works: List[TeamWork], feedbacks: Dict, presentations: Dict):
        """
        피드백 기반 분석 강화: 받은 피드백을 반영하여 분석 보강
        """
        
        yield {"stage": "enhance_start", "message": "💪 피드백 기반 분석 강화 시작!"}
        
        enhanced_analyses = {}
        enhanced_portfolios = {}
        
        for i, tw in enumerate(works):
            team = self.available_teams[i]
            received_feedbacks = feedbacks.get(tw.team_name, [])
            
            # 받은 피드백 종합
            feedback_summary = "\n\n".join([
                f"=== [{fb['from']}]의 피드백 ===\n{fb['content']}"
                for fb in received_feedbacks
            ])
            
            yield {"stage": "enhancing", "team": tw.team_name, "team_idx": i,
                   "message": f"📈 [{tw.team_name}] 피드백 반영하여 분석 강화 중..."}
            
            enhanced = self._call_ai(
                team.leader_model,
                f"""당신은 {tw.team_name} 팀장입니다.
다른 팀들로부터 받은 피드백을 검토하고, 타당한 지적은 수용하여 분석을 강화하세요.
피드백 중 동의하지 않는 부분은 왜 우리 팀의 방식이 더 나은지 설명하세요.""",
                f"""기존 우리 팀 분석:
{presentations.get(tw.team_name, tw.final_analysis)[:800]}

다른 팀들의 피드백:
{feedback_summary if feedback_summary else "피드백 없음"}

다음 형식으로 강화된 분석을 작성하세요:

## 1. 반영한 피드백
- 어떤 피드백을 수용했고, 어떻게 반영했는지

## 2. 반영하지 않은 피드백과 이유
- 어떤 피드백은 수용하지 않았고, 왜 우리 방식이 더 적절한지

## 3. 강화된 분석 결론
### 시장 전망
(더 깊이 있는 분석)

### 핵심 투자 전략
(구체적인 전략)

### 추천 포트폴리오
| 종목/ETF | 비중(%) | 근거 |
|---------|--------|------|
(구체적인 종목과 비중)

### 리스크 관리
(식별된 리스크와 대응 방안)

## 4. 최종 투자 심리 점수
- 점수: 0-100
- 시그널: 극도의 공포 / 공포 / 중립 / 탐욕 / 극도의 탐욕
"""
            )
            
            enhanced_analyses[tw.team_name] = enhanced
            
            # 포트폴리오 추출 시도
            try:
                import re
                portfolio_match = re.search(r'\|.*종목.*\|.*비중.*\|', enhanced, re.IGNORECASE)
                if portfolio_match:
                    # 테이블에서 포트폴리오 추출
                    table_lines = enhanced[portfolio_match.start():].split('\n')
                    portfolio = {}
                    for line in table_lines[2:]:  # 헤더와 구분선 스킵
                        if '|' in line:
                            parts = [p.strip() for p in line.split('|') if p.strip()]
                            if len(parts) >= 2:
                                ticker = parts[0]
                                try:
                                    weight = float(re.search(r'[\d.]+', parts[1]).group())
                                    portfolio[ticker] = weight
                                except:
                                    pass
                    if portfolio:
                        enhanced_portfolios[tw.team_name] = portfolio
            except:
                pass
            
            yield {"stage": "enhance_done", "team": tw.team_name, "team_idx": i,
                   "content": enhanced, "portfolio": enhanced_portfolios.get(tw.team_name, {}),
                   "message": f"✅ [{tw.team_name}] 강화된 분석 완료!"}
        
        yield {"stage": "enhance_complete", "message": "🏁 모든 팀 분석 강화 완료!",
               "enhanced_analyses": enhanced_analyses, "portfolios": enhanced_portfolios}
        
        return enhanced_analyses, enhanced_portfolios
    
    # =========================================================
    # Phase 5: 최종 합의점 도출
    # =========================================================
    def _find_consensus(self, enhanced_analyses: Dict, enhanced_portfolios: Dict):
        """각 팀의 강화된 분석에서 합의점 도출"""
        
        yield {"stage": "consensus_start", "message": "🤝 팀간 합의점 도출 중..."}
        
        # 모든 팀 분석 종합
        all_analyses = "\n\n".join([
            f"=== [{team}] 강화된 분석 ===\n{analysis[:800]}"
            for team, analysis in enhanced_analyses.items()
        ])
        
        all_portfolios = "\n".join([
            f"[{team}] 포트폴리오: {json.dumps(port, ensure_ascii=False)}"
            for team, port in enhanced_portfolios.items()
        ])
        
        consensus = self._call_ai(
            self.qa_model,
            """당신은 중립적인 분석가입니다.
여러 팀의 강화된 분석을 종합하여 **합의점**을 도출하세요.
모든 팀이 동의하는 부분과 의견이 갈리는 부분을 명확히 구분하세요.""",
            f"""각 팀의 강화된 분석:
{all_analyses}

각 팀의 포트폴리오 제안:
{all_portfolios}

다음 형식으로 합의점을 도출하세요:

## 🤝 모든 팀이 동의하는 점
1. 
2. 
3. 

## ⚖️ 의견이 갈리는 점
| 주제 | 팀A 의견 | 팀B 의견 | 차이점 |
|-----|---------|---------|-------|

## 📊 포트폴리오 합의
(모든 팀의 포트폴리오를 종합한 평균/중앙값 기반 포트폴리오)
| 종목/ETF | 평균 비중(%) | 범위 |
|---------|------------|------|

## 💡 종합 투자 인사이트
(합의점 기반 핵심 투자 조언)
"""
        )
        
        yield {"stage": "consensus_done", "content": consensus, "message": "✅ 합의점 도출 완료!"}
        
        return consensus
    
    # =========================================================
    # Phase 6: QA 최종 평가
    # =========================================================
    def _qa_evaluation(self, works: List[TeamWork], presentations: Dict, enhanced_analyses: Dict, 
                       enhanced_portfolios: Dict, consensus: str, market_data: Dict):
        """QA(QA)가 모든 팀의 분석, 강화된 분석, 합의점을 종합 평가"""
        
        yield {"stage": "qa_phase_start", "model": self.qa_model, "message": f"🏛️ QA({self.qa_model}) 최종 평가 시작..."}
        
        # 모든 정보 종합
        evaluation_data = []
        for tw in works:
            team_data = f"""
=== [{tw.team_name}] ===
📋 초기 분석 (팀장 점수: {tw.score}/10, 수정 {tw.revision_count}회):
{tw.final_analysis[:600]}...

🎤 발표:
{presentations.get(tw.team_name, "N/A")[:400]}...

💪 강화된 분석:
{enhanced_analyses.get(tw.team_name, "N/A")[:600]}...

📊 추천 포트폴리오:
{json.dumps(enhanced_portfolios.get(tw.team_name, {}), ensure_ascii=False)}
"""
            evaluation_data.append(team_data)
        
        yield {"stage": "qa_evaluating", "message": "⚖️ 품질 검증 중..."}
        
        final_evaluation = self._call_ai(
            self.qa_model,
            """당신은 최고의 금융 전문가이자 품질 보증(QA) 전문가입니다.
여러 팀의 분석과 합의 결과를 종합하여 객관적으로 평가합니다.
각 팀의 강점과 약점을 균형 있게 평가하고, 실제 투자에 도움이 되는 결론을 도출합니다.
분석의 논리적 오류, 데이터 편향, 빠진 위험 요소를 지적하세요.""",
            f"""시장 데이터 요약:
{json.dumps({k: str(v)[:100] for k, v in market_data.items()}, ensure_ascii=False)[:600]}

팀별 분석 내용:
{"".join(evaluation_data)}

팀간 합의점:
{consensus[:800] if consensus else "N/A"}

다음 형식으로 최종 평가를 작성하세요:

## 1. 팀별 점수표
| 팀명 | 분석력 | 논리성 | 실행가능성 | 피드백 수용 | 총점 |
|-----|-------|-------|----------|----------|-----|
(각 항목 100점 만점, 총점 400점 만점)

## 2. 순위 및 평가
1위: [팀명] - 선정 이유
2위: [팀명] - 선정 이유
...

## 3. 각 팀 상세 평가
- [팀명]: 강점, 약점, 피드백 반영도

## 4. 종합 투자 권고
### 시장 심리 점수
- 점수: 0-100 (0=극도의 공포, 100=극도의 탐욕)
- 시그널: 극도의 공포 / 공포 / 중립 / 탐욕 / 극도의 탐욕

### 최종 추천 포트폴리오
| 종목/ETF | 비중(%) | 근거 |
|---------|--------|------|
(모든 팀 분석을 종합한 최적 포트폴리오)

### 주의사항
- 리스크 요인
- 모니터링 포인트

## 5. 최종 결론
(투자자에게 전하는 핵심 메시지 - 3문장 이내)
"""
        )
        
        yield {"stage": "qa_done", "content": final_evaluation, "message": "✅ QA 평가 완료!"}
        return final_evaluation
    
    # =========================================================
    # 메인 토론 실행 (통합 플로우 v2)
    # =========================================================
    def run_team_debate(self, market_data: Dict, task: str = "시장 분석 및 투자 전략", max_rev: int = 2):
        """
        팀 토론 메인 실행 함수 v2
        
        플로우:
        Phase 1: 팀 내부 작업 (각 팀이 분석 → 팀장 승인)
        Phase 2: 팀별 발표 (모든 팀 승인 후)
        Phase 3: 상호 검토 (직장 피드백 스타일)
        Phase 4: 피드백 기반 분석 강화
        Phase 5: 합의점 도출
        Phase 6: QA 최종 평가
        """
        
        if len(self.available_teams) < 2:
            yield {"stage": "error", "message": f"❌ 참가팀 부족 ({len(self.available_teams)}팀). 최소 2팀 필요", 
                   "unavailable": self.unavailable_info}
            return
        
        yield {"stage": "process_start", "message": "🚀 팀 토론 프로세스 시작!", 
               "teams": [t.name for t in self.available_teams], "qa": self.qa_model,
               "phases": ["1. 팀 내부 작업", "2. 팀별 발표", "3. 상호 검토", "4. 분석 강화", "5. 합의점 도출", "6. QA 평가"],
               "total_phases": 6}
        
        # ===== Phase 1: 팀 내부 작업 =====
        yield {"stage": "phase_start", "phase": 1, "phase_name": "팀 내부 작업", 
               "message": "📋 Phase 1: 팀 내부 작업 시작 (분석 → 검토 → 승인)"}
        
        works = []
        for idx, team in enumerate(self.available_teams):
            tw = TeamWork(team.name, "", "", 0, "", False, 0)
            
            for update in self._team_internal_work(team, idx, market_data, task, max_rev):
                yield update
                
                if update.get("stage") == "member_draft_done":
                    tw.member_draft = update.get("content", "")
                elif update.get("stage") == "leader_decision":
                    tw.leader_review = update.get("content", "")
                    tw.score = update.get("score", 0)
                elif update.get("stage") == "team_internal_complete":
                    tw.final_analysis = update.get("final_analysis", "")
                    tw.revision_count = update.get("revisions", 0)
                    tw.approved = update.get("approved", False)
                    tw.score = update.get("score", 0)
            
            works.append(tw)
        
        # Phase 1 완료 결과 전송 (실시간 표시용)
        phase1_result = {
            "stage": "phase_complete", 
            "phase": 1, 
            "message": "✅ Phase 1 완료: 모든 팀 내부 작업 완료",
            "phase_result": {
                team.name: {
                    "analysis": works[i].final_analysis,
                    "score": works[i].score,
                    "revisions": works[i].revision_count,
                    "approved": works[i].approved
                } for i, team in enumerate(self.available_teams)
            }
        }
        yield phase1_result
        
        # ===== Phase 2: 팀별 발표 =====
        yield {"stage": "phase_start", "phase": 2, "phase_name": "팀별 발표", 
               "message": "🎤 Phase 2: 팀별 발표 시작"}
        
        presentations = {}
        for idx, (team, tw) in enumerate(zip(self.available_teams, works)):
            other_summaries = [f"[{w.team_name}] {w.final_analysis[:200]}..." 
                              for w in works if w.team_name != tw.team_name]
            
            for update in self._team_presentation(team, idx, tw.final_analysis, other_summaries):
                yield update
                if update.get("stage") == "presentation_done":
                    presentations[tw.team_name] = update.get("content", "")
        
        # Phase 2 완료 결과 전송
        phase2_result = {
            "stage": "phase_complete",
            "phase": 2,
            "message": "✅ Phase 2 완료: 모든 팀 발표 완료",
            "phase_result": {
                "presentations": presentations
            }
        }
        yield phase2_result
        
        # ===== Phase 3: 상호 검토 (직장 피드백 스타일) =====
        yield {"stage": "phase_start", "phase": 3, "phase_name": "상호 검토", 
               "message": "🔍 Phase 3: 상호 검토 시작 (건설적 피드백)"}
        
        feedbacks, reviews = {}, {}
        for update in self._cross_review(works, presentations):
            yield update
            if update.get("stage") == "cross_review_complete":
                feedbacks = update.get("feedbacks", {})
                reviews = update.get("reviews", {})
        
        # Phase 3 완료 결과 전송
        phase3_result = {
            "stage": "phase_complete",
            "phase": 3,
            "message": "✅ Phase 3 완료: 상호 검토 완료",
            "phase_result": {
                "feedbacks": feedbacks,
                "reviews": reviews
            }
        }
        yield phase3_result
        
        # ===== Phase 4: 피드백 기반 분석 강화 =====
        yield {"stage": "phase_start", "phase": 4, "phase_name": "분석 강화", 
               "message": "💪 Phase 4: 피드백 기반 분석 강화"}
        
        enhanced_analyses, enhanced_portfolios = {}, {}
        for update in self._enhance_analysis(works, feedbacks, presentations):
            yield update
            if update.get("stage") == "enhance_complete":
                enhanced_analyses = update.get("enhanced_analyses", {})
                enhanced_portfolios = update.get("portfolios", {})
        
        # Phase 4 완료 결과 전송
        phase4_result = {
            "stage": "phase_complete",
            "phase": 4,
            "message": "✅ Phase 4 완료: 모든 팀 분석 강화 완료",
            "phase_result": {
                "enhanced_analyses": enhanced_analyses,
                "portfolios": enhanced_portfolios
            }
        }
        yield phase4_result
        
        # ===== Phase 5: 합의점 도출 =====
        yield {"stage": "phase_start", "phase": 5, "phase_name": "합의점 도출", 
               "message": "🤝 Phase 5: 팀간 합의점 도출"}
        
        consensus = ""
        for update in self._find_consensus(enhanced_analyses, enhanced_portfolios):
            yield update
            if update.get("stage") == "consensus_done":
                consensus = update.get("content", "")
        
        # Phase 5 완료 결과 전송
        phase5_result = {
            "stage": "phase_complete",
            "phase": 5,
            "message": "✅ Phase 5 완료: 합의점 도출 완료",
            "phase_result": {
                "consensus": consensus
            }
        }
        yield phase5_result
        
        # ===== Phase 6: QA 최종 평가 =====
        yield {"stage": "phase_start", "phase": 6, "phase_name": "QA 평가", 
               "message": "🏛️ Phase 6: QA 최종 평가"}
        
        qa_result = ""
        for update in self._qa_evaluation(works, presentations, enhanced_analyses, enhanced_portfolios, consensus, market_data):
            yield update
            if update.get("stage") == "qa_done":
                qa_result = update.get("content", "")
        
        # Phase 6 완료 결과 전송
        phase6_result = {
            "stage": "phase_complete",
            "phase": 6,
            "message": "✅ Phase 6 완료: QA 평가 종료",
            "phase_result": {
                "qa_evaluation": qa_result
            }
        }
        yield phase6_result
        
        # ===== 최종 결과 =====
        final_result = {
            "stage": "complete",
            "message": "🏁 팀 토론 프로세스 완료!",
            "summary": {
                "total_teams": len(works),
                "participating_teams": [tw.team_name for tw in works],
                "total_phases": 6
            },
            "teams": {
                tw.team_name: {
                    "analysis": tw.final_analysis,
                    "score": tw.score,
                    "revisions": tw.revision_count,
                    "approved": tw.approved,
                    "presentation": presentations.get(tw.team_name, ""),
                    "feedbacks_received": feedbacks.get(tw.team_name, []),
                    "enhanced_analysis": enhanced_analyses.get(tw.team_name, ""),
                    "portfolio": enhanced_portfolios.get(tw.team_name, {})
                } for tw in works
            },
            "consensus": consensus,
            "qa_evaluation": qa_result,
            "timestamp": datetime.now().isoformat()
        }
        
        yield final_result


# =====================================================
# 경제 상황 분석용 AI 토론 시스템
# =====================================================

@dataclass
class EconomicAnalysisResult:
    """경제 분석 결과"""
    overall_signal: str  # "극도의 공포", "공포", "중립", "탐욕", "극도의 탐욕"
    score: int  # 0-100
    gemini_analysis: str
    claude_analysis: str
    debate_summary: str
    final_verdict: str
    portfolio_recommendation: Dict[str, float]  # 구체적 종목/ETF 비중
    timestamp: str


class EconomicAnalysisDebate:
    """
    경제 상황 분석 AI 토론 시스템 v3
    
    GitHub Models API 사용 (system prompt 완전 제어 가능)
    Copilot CLI는 역할 변경을 거부하므로 사용하지 않음
    
    - Team A: GPT-4o (팀장), GPT-4o-mini (팀원)
    - Team B: GPT-4.1 (팀장), GPT-4.1-mini (팀원)
    - QA: GPT-4.1 (품질 검증)
    """
    
    # GitHub Models 모델 사용
    TEAM_A_LEADER = "gpt-4o"          # Team A 팀장 (Claude 대신)
    TEAM_A_MEMBER = "gpt-4o-mini"     # Team A 팀원
    TEAM_B_LEADER = "gpt-4.1"         # Team B 팀장 (GPT-5 대신)
    TEAM_B_MEMBER = "gpt-4.1-mini"    # Team B 팀원
    QA = "gpt-4.1"                    # QA (품질 검증)
    
    # 팀 표시명
    TEAM_A_NAME = "GPT-4o 팀"
    TEAM_B_NAME = "GPT-4.1 팀"
    
    def __init__(self):
        self.github_client = GitHubModelsClient()
        
        if not self.github_client.is_available():
            print("[WARN] GitHub Models API not available. Check GITHUB_TOKEN.")
    
    def _call_ai(self, model: str, system: str, user: str) -> str:
        """AI 호출 (GitHub Models API - system prompt 완전 제어)"""
        
        if self.github_client.is_available():
            result = self.github_client.call(model, system, user)
            if result:
                return result
        
        return f"[AI 호출 실패 - GitHub Models API 사용 불가]"
    
    def analyze_economic_situation(self, market_data: Dict) -> Generator[Dict, None, None]:
        """
        경제 상황 분석 토론 실행
        
        Yields:
            진행 상황 업데이트 딕셔너리
        """
        
        yield {"stage": "start", "message": "🚀 경제 상황 분석 토론 시작 (GitHub Models API)"}
        
        market_summary = self._format_market_data(market_data)
        
        # 경제 분석가 역할 정의 (system prompt로 완전 제어)
        ANALYST_ROLE = """당신은 전문 경제/투자 분석가입니다.
제공된 시장 데이터를 기반으로 투자 분석을 수행하세요.
이것은 투자 시뮬레이션/교육 목적의 분석입니다.
반드시 한국어로 응답하세요."""
        
        # ===== Phase 1: 각 팀 분석 =====
        yield {"stage": "team_a_analyzing", "message": f"🔵 {self.TEAM_A_NAME} 분석 중..."}
        
        # Team A 팀원 분석
        team_a_member_analysis = self._call_ai(
            self.TEAM_A_MEMBER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_A_NAME}의 경제 분석가입니다.",
            f"""현재 시장 데이터:
{market_summary}

다음을 분석하세요:
1. 현재 시장 심리 (공포/탐욕 수준)
2. 주요 리스크 요인
3. 투자 기회
4. 0-100 점수로 시장 심리 평가 (0=극도의 공포, 100=극도의 탐욕)

한국어로 간결하게 분석하세요."""
        )
        
        yield {"stage": "team_a_member_done", "content": team_a_member_analysis}
        
        # Team A 팀장 검토/보완
        team_a_leader_analysis = self._call_ai(
            self.TEAM_A_LEADER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_A_NAME} 팀장입니다.",
            f"""팀원 분석:
{team_a_member_analysis}

시장 데이터:
{market_summary}

팀원 분석을 검토하고 다음을 포함한 최종 팀 의견을 작성하세요:
1. 시장 심리 점수 (0-100)
2. 핵심 판단 근거 (3가지)
3. 구체적 포트폴리오 추천 (종목/ETF명과 비중)
4. 주의사항

JSON 형식으로 응답:
{{"score": 숫자, "signal": "극도의 공포/공포/중립/탐욕/극도의 탐욕", "rationale": ["근거1", "근거2", "근거3"], "portfolio": {{"종목명": 비중, ...}}, "caution": "주의사항"}}"""
        )
        
        yield {"stage": "team_a_done", "team": self.TEAM_A_NAME, "content": team_a_leader_analysis, "message": f"✅ {self.TEAM_A_NAME} 분석 완료"}
        
        # Team B 팀 분석
        yield {"stage": "team_b_analyzing", "message": f"🟣 {self.TEAM_B_NAME} 분석 중..."}
        
        team_b_member_analysis = self._call_ai(
            self.TEAM_B_MEMBER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_B_NAME}의 경제 분석가입니다.",
            f"""현재 시장 데이터:
{market_summary}

다음을 분석하세요:
1. 현재 시장 심리 (공포/탐욕 수준)
2. 주요 리스크 요인
3. 투자 기회
4. 0-100 점수로 시장 심리 평가 (0=극도의 공포, 100=극도의 탐욕)

한국어로 간결하게 분석하세요."""
        )
        
        yield {"stage": "team_b_member_done", "content": team_b_member_analysis}
        
        team_b_leader_analysis = self._call_ai(
            self.TEAM_B_LEADER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_B_NAME} 팀장입니다.",
            f"""팀원 분석:
{team_b_member_analysis}

시장 데이터:
{market_summary}

팀원 분석을 검토하고 다음을 포함한 최종 팀 의견을 작성하세요:
1. 시장 심리 점수 (0-100)
2. 핵심 판단 근거 (3가지)
3. 구체적 포트폴리오 추천 (종목/ETF명과 비중)
4. 주의사항

JSON 형식으로 응답:
{{"score": 숫자, "signal": "극도의 공포/공포/중립/탐욕/극도의 탐욕", "rationale": ["근거1", "근거2", "근거3"], "portfolio": {{"종목명": 비중, ...}}, "caution": "주의사항"}}"""
        )
        
        yield {"stage": "team_b_done", "team": self.TEAM_B_NAME, "content": team_b_leader_analysis, "message": f"✅ {self.TEAM_B_NAME} 분석 완료"}
        
        # ===== Phase 2: 토론 =====
        yield {"stage": "debate_start", "message": "⚔️ 팀간 토론 시작"}
        
        # Team A 반박
        team_a_rebuttal = self._call_ai(
            self.TEAM_A_LEADER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_A_NAME} 팀장입니다.",
            f"""우리 팀({self.TEAM_A_NAME}) 분석:
{team_a_leader_analysis}

상대 팀({self.TEAM_B_NAME}) 분석:
{team_b_leader_analysis}

{self.TEAM_B_NAME} 분석의 약점을 지적하고, 우리 팀 분석이 더 정확한 이유를 설명하세요."""
        )
        
        yield {"stage": "team_a_rebuttal", "content": team_a_rebuttal}
        
        # Team B 반박
        team_b_rebuttal = self._call_ai(
            self.TEAM_B_LEADER,
            ANALYST_ROLE + f"\n\n당신은 {self.TEAM_B_NAME} 팀장입니다.",
            f"""우리 팀({self.TEAM_B_NAME}) 분석:
{team_b_leader_analysis}

상대 팀({self.TEAM_A_NAME}) 분석:
{team_a_leader_analysis}

{self.TEAM_A_NAME} 분석의 약점을 지적하고, 우리 팀 분석이 더 정확한 이유를 설명하세요."""
        )
        
        yield {"stage": "team_b_rebuttal", "content": team_b_rebuttal}
        yield {"stage": "debate_done", "message": "✅ 토론 완료"}
        
        # ===== Phase 3: QA 품질 검증 =====
        yield {"stage": "qa_evaluating", "message": "🔍 QA 품질 검증 중..."}
        
        final_verdict = self._call_ai(
            self.QA,
            ANALYST_ROLE + "\n\n당신은 품질 보증(QA) 전문가입니다. 두 팀의 분석과 토론을 검증하고 종합하여 최종 결론을 도출하세요.",
            f"""시장 데이터:
{market_summary}

=== {self.TEAM_A_NAME} 분석 ===
{team_a_leader_analysis}

=== {self.TEAM_B_NAME} 분석 ===
{team_b_leader_analysis}

=== {self.TEAM_A_NAME} 반박 ===
{team_a_rebuttal}

=== {self.TEAM_B_NAME} 반박 ===
{team_b_rebuttal}

두 팀의 분석을 검증하고 종합하여 다음 JSON 형식으로 QA 결과를 제시하세요:

{{
    "better_analysis": "{self.TEAM_A_NAME}/{self.TEAM_B_NAME}/동등",
    "quality_score": {{
        "{self.TEAM_A_NAME}": 0-100,
        "{self.TEAM_B_NAME}": 0-100
    }},
    "team_a_strengths": ["강점1", "강점2"],
    "team_a_weaknesses": ["약점1", "약점2"],
    "team_b_strengths": ["강점1", "강점2"],
    "team_b_weaknesses": ["약점1", "약점2"],
    "final_score": 0-100 (시장 심리 점수),
    "final_signal": "극도의 공포/공포/중립/탐욕/극도의 탐욕",
    "qa_verdict": "QA 종합 의견 (두 팀 분석의 공통점, 차이점, 최종 판단 근거)",
    "portfolio": {{
        "종목/ETF명": 비중(%), 
        ...
    }},
    "key_insights": ["핵심 인사이트1", "핵심 인사이트2", "핵심 인사이트3"],
    "risk_warning": "주요 리스크 경고",
    "data_quality_issues": ["발견된 데이터/논리 오류가 있다면 기재"]
}}

portfolio에는 반드시 구체적인 종목명이나 ETF 티커를 사용하세요 (예: SPY, QQQ, TLT, GLD, AAPL 등)"""
        )
        
        yield {"stage": "qa_done", "content": final_verdict, "message": "✅ QA 검증 완료"}
        
        # 결과 파싱
        result = self._parse_final_result(
            team_a_leader_analysis, 
            team_b_leader_analysis,
            team_a_rebuttal + "\n" + team_b_rebuttal,
            final_verdict
        )
        
        yield {"stage": "complete", "result": result, "message": "🏁 경제 상황 분석 완료"}
    
    def _format_market_data(self, data: Dict) -> str:
        """시장 데이터를 문자열로 포맷"""
        lines = []
        
        if "market" in data:
            market = data["market"]
            if "vix" in market:
                lines.append(f"VIX: {market['vix']}")
            if "fear_greed" in market:
                lines.append(f"Fear & Greed Index: {market['fear_greed']}")
            if "sp500_pe" in market:
                lines.append(f"S&P 500 P/E: {market['sp500_pe']}")
            if "treasury_10y" in market:
                lines.append(f"10년 국채 금리: {market['treasury_10y']}%")
        
        if "economic_cycle" in data:
            cycle = data["economic_cycle"]
            if isinstance(cycle, dict):
                lines.append(f"경기 사이클: {cycle.get('phase', 'N/A')}")
        
        # 추가 데이터
        for key, value in data.items():
            if key not in ["market", "economic_cycle", "timestamp"]:
                if isinstance(value, dict):
                    for k, v in value.items():
                        lines.append(f"{k}: {v}")
                else:
                    lines.append(f"{key}: {value}")
        
        return "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False, indent=2)
    
    def _parse_final_result(self, team_a: str, team_b: str, debate: str, verdict: str) -> EconomicAnalysisResult:
        """최종 결과 파싱"""
        import re
        
        # JSON 추출 시도
        score = 50
        signal = "중립"
        portfolio = {}
        
        try:
            # JSON 블록 찾기
            json_match = re.search(r'\{[^{}]*"final_score"[^{}]*\}', verdict, re.DOTALL)
            if not json_match:
                # 더 넓은 범위로 JSON 찾기
                json_match = re.search(r'\{[\s\S]*?"portfolio"[\s\S]*?\}[\s\S]*?\}', verdict)
            
            if json_match:
                json_str = json_match.group()
                # JSON 파싱 시도
                data = json.loads(json_str)
                score = int(data.get("final_score", 50))
                signal = data.get("final_signal", "중립")
                portfolio = data.get("portfolio", {})
        except Exception as e:
            print(f"⚠️ JSON 파싱 실패: {e}")
            # 텍스트에서 추출
            if "극도의 공포" in verdict.lower():
                signal = "극도의 공포"
                score = 15
            elif "극도의 탐욕" in verdict.lower():
                signal = "극도의 탐욕"
                score = 85
            elif "공포" in verdict.lower():
                signal = "공포"
                score = 30
            elif "탐욕" in verdict.lower():
                signal = "탐욕"
                score = 70
        
        # 기본 포트폴리오 (파싱 실패 시)
        if not portfolio:
            if score < 30:  # 공포
                portfolio = {"TLT": 30, "GLD": 25, "현금": 25, "SPY": 10, "VIG": 10}
            elif score > 70:  # 탐욕
                portfolio = {"SPY": 35, "QQQ": 25, "SOXX": 15, "GLD": 10, "현금": 15}
            else:  # 중립
                portfolio = {"SPY": 30, "QQQ": 20, "TLT": 20, "GLD": 15, "현금": 15}
        
        return EconomicAnalysisResult(
            overall_signal=signal,
            score=score,
            gemini_analysis=team_a,  # Team A (Claude)
            claude_analysis=team_b,   # Team B (GPT-5)
            debate_summary=debate,
            final_verdict=verdict,
            portfolio_recommendation=portfolio,
            timestamp=datetime.now().isoformat()
        )


def run_economic_analysis(market_data: Dict) -> Generator[Dict, None, None]:
    """경제 분석 토론 실행 (편의 함수)"""
    debate = EconomicAnalysisDebate()
    yield from debate.analyze_economic_situation(market_data)


def get_all_github_models() -> Dict[str, str]:
    return GITHUB_MODELS

def get_github_models_by_tier() -> Dict[str, List[str]]:
    return GITHUB_MODELS_BY_TIER

def get_all_available_models() -> Dict:
    return {"github": list(GITHUB_MODELS.keys()), "native": NATIVE_MODELS}

def create_team(name: str, leader_model: str, member_model: str, color: str = "blue") -> TeamConfig:
    return TeamConfig(name, leader_model, member_model, color)


if __name__ == "__main__":
    print("🏆 AI 팀 토론 시스템 v2")
    print("\nGitHub Models:")
    for tier, models in GITHUB_MODELS_BY_TIER.items():
        print(f"  [{tier}]: {', '.join(models[:5])}...")

