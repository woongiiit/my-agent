"""Hugging Face / LiteLLM 모델 설정."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# LiteLLM이 Hugging Face 인증에 사용
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "openai/gpt-oss-120b")
# 비우면 HF Inference API 기본 라우팅: huggingface/openai/gpt-oss-120b
# 예: together, fireworks-ai, sambanova
HF_INFERENCE_PROVIDER = os.getenv("HF_INFERENCE_PROVIDER", "").strip()
HF_API_BASE = os.getenv("HF_API_BASE", "").strip()

# gpt-oss 등 reasoning 모델이 ADK→LiteLLM 변환 시 넣는 필드.
# HF Router API는 요청 payload에서 이 필드를 거부함.
_HF_UNSUPPORTED_MESSAGE_KEYS = frozenset(
    {"reasoning_content", "reasoning", "thinking_blocks"}
)


def _strip_unsupported_hf_fields(messages: list[Any]) -> list[Any]:
    cleaned: list[Any] = []
    for msg in messages:
        if isinstance(msg, dict):
            msg = {
                key: value
                for key, value in msg.items()
                if key not in _HF_UNSUPPORTED_MESSAGE_KEYS
            }
        cleaned.append(msg)
    return cleaned


class HuggingFaceLiteLlm(LiteLlm):
    """HF Inference API 호환용 LiteLlm — reasoning 필드를 요청에서 제거."""

    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, **kwargs)
        original_acompletion = self.llm_client.acompletion

        async def sanitized_acompletion(**completion_args):
            messages = completion_args.get("messages")
            if messages:
                completion_args = {
                    **completion_args,
                    "messages": _strip_unsupported_hf_fields(messages),
                }
            return await original_acompletion(**completion_args)

        self.llm_client.acompletion = sanitized_acompletion


def _build_hf_model_name() -> str:
    explicit = os.getenv("HF_MODEL", "").strip()
    if explicit:
        return explicit

    if HF_INFERENCE_PROVIDER:
        return f"huggingface/{HF_INFERENCE_PROVIDER}/{HF_MODEL_ID}"

    return f"huggingface/{HF_MODEL_ID}"


def create_llm() -> LiteLlm:
    """환경변수 기반 LiteLLM 모델 인스턴스를 생성합니다."""
    if HF_TOKEN:
        os.environ.setdefault("HF_TOKEN", HF_TOKEN)

    model_name = _build_hf_model_name()
    kwargs: dict = {}

    if HF_API_BASE:
        kwargs["api_base"] = HF_API_BASE

    return HuggingFaceLiteLlm(model=model_name, **kwargs)
