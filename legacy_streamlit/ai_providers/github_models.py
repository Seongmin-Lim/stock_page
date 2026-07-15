"""
GitHub Models AI 클라이언트
GitHub에서 호스팅하는 다양한 AI 모델 사용 (GPT-4o, Llama, Mistral, Phi 등)
"""
import os
from typing import Optional
from openai import OpenAI


class GitHubModelsClient:
    """GitHub Models API 클라이언트"""
    
    # 실제 테스트 완료된 모델들 (2025년 6월 검증)
    AVAILABLE_MODELS = {
        # OpenAI 모델 (✅ 검증됨)
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4.1": "gpt-4.1",
        "gpt-4.1-mini": "gpt-4.1-mini",
        "gpt-4.1-nano": "gpt-4.1-nano",
        
        # Meta Llama 모델 (✅ 검증됨)
        "llama-3.3-70b": "Llama-3.3-70B-Instruct",
        "llama-3.2-90b-vision": "Llama-3.2-90B-Vision-Instruct",
        
        # Microsoft Phi 모델 (✅ 검증됨)
        "phi-4": "Phi-4",
        "phi-4-mini": "Phi-4-mini-instruct",
        
        # DeepSeek 모델 (✅ 검증됨)
        "deepseek-r1": "DeepSeek-R1",
        "deepseek-r1-0528": "DeepSeek-R1-0528",
        
        # Mistral 모델 (✅ 검증됨)
        "codestral": "Codestral-2501",
    }
    
    def __init__(self, model: str = "gpt-4o-mini", token: str = None):
        """
        Args:
            model: 사용할 모델 (기본: gpt-4o-mini)
            token: GitHub Personal Access Token (없으면 환경변수에서 로드)
        """
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
        
        if not self.token:
            raise ValueError(
                "GitHub Token이 필요합니다. "
                "GITHUB_TOKEN 또는 GITHUB_PAT 환경변수를 설정하거나 "
                "token 파라미터로 전달하세요."
            )
        
        # 모델 이름 매핑
        self.model = self.AVAILABLE_MODELS.get(model, model)
        self.model_key = model
        
        # OpenAI SDK를 GitHub Models 엔드포인트로 설정
        self.client = OpenAI(
            base_url="https://models.github.ai/inference",  # 올바른 GitHub Models 엔드포인트
            api_key=self.token
        )
    
    def chat(self, 
             messages: list,
             temperature: float = 0.7,
             max_tokens: int = 4000,
             stream: bool = False) -> str:
        """
        채팅 완성 API 호출
        
        Args:
            messages: 메시지 리스트 [{"role": "user", "content": "..."}]
            temperature: 창의성 조절 (0-1)
            max_tokens: 최대 토큰 수
            stream: 스트리밍 여부
            
        Returns:
            AI 응답 텍스트
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                return response  # 스트림 객체 반환
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"GitHub Models API 오류: {str(e)}"
    
    def analyze(self, prompt: str, system_prompt: str = None) -> str:
        """
        간단한 분석 요청
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)
            
        Returns:
            AI 응답
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return self.chat(messages)
    
    @classmethod
    def list_models(cls) -> dict:
        """사용 가능한 모델 목록 반환"""
        return cls.AVAILABLE_MODELS
    
    @classmethod
    def get_model_info(cls) -> str:
        """모델 정보 문자열 반환"""
        info = "📋 GitHub Models 사용 가능 모델:\n\n"
        
        categories = {
            "OpenAI": ["gpt-4o", "gpt-4o-mini"],
            "Meta Llama": ["llama-3.1-405b", "llama-3.1-70b", "llama-3.1-8b", "llama-3.2-90b", "llama-3.2-11b"],
            "Mistral": ["mistral-large", "mistral-small", "mistral-nemo"],
            "Microsoft Phi": ["phi-4", "phi-3.5-mini", "phi-3.5-moe"],
            "Cohere": ["cohere-command-r", "cohere-command-r-plus"],
            "AI21": ["jamba-1.5-large", "jamba-1.5-mini"]
        }
        
        for category, models in categories.items():
            info += f"**{category}**\n"
            for model in models:
                info += f"  - {model}\n"
            info += "\n"
        
        return info


# 테스트
if __name__ == "__main__":
    print(GitHubModelsClient.get_model_info())
    
    # 토큰이 있으면 테스트
    try:
        client = GitHubModelsClient(model="gpt-4o-mini")
        response = client.analyze("한국의 수도는 어디인가요?")
        print(f"\n테스트 응답: {response}")
    except ValueError as e:
        print(f"\n⚠️ {e}")
