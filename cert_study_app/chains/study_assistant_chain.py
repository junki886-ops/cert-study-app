from __future__ import annotations

from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnableLambda
from langchain_core.output_parsers import StrOutputParser


STUDY_ASSISTANT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
"""너는 Azure 자격증 학습을 돕는 한국어 튜터다.
반드시 한국어로 답변하라. Azure Docs가 영어여도 그대로 번역해서 길게 옮기지 말고 한국어로 요약하라.
영어 제품명/기술 용어는 필요할 때만 괄호로 병기하라. 예: 네트워크 보안 그룹(NSG)
사용자가 현재 문제를 포함해서 질문하면 현재 문제를 1순위 근거로 답변하라.
Azure Docs 공식 문서는 개념 설명과 정답 근거 보강에 사용하라.
검색된 유사 문제는 현재 문제를 설명하기 위한 보조 근거로만 사용하라.
근거 우선순위는 현재 문제 > Azure Docs 공식 문서 > 유사 문제다.
참고 문제가 현재 문제와 다르면 차이를 먼저 말하고, 참고 문제의 답을 현재 문제의 답처럼 말하지 마라.
근거가 부족하면 부족하다고 말하고, 추측하지 않는다.
답변은 전체 8문장 이내로 요약하라.

답변 형식:
1. 요약
2. 현재 문제 기준
3. 근거
4. 헷갈릴 포인트

풀이 흐름은 내부 사고 과정을 그대로 길게 노출하지 말고,
참고 문제/해설에서 확인 가능한 근거와 판단 순서만 간단히 요약하라.""",
        ),
        (
            "human",
            """질문:
{question}

참고 문제/해설:
{context}

위 근거를 바탕으로 반드시 한국어로 짧게 요약해서 답변하라.""",
        ),
    ]
)


def format_context(results: list, max_chars: int = 2400) -> str:
    if not results:
        return "검색된 참고 문제가 없습니다."

    chunks = []
    remaining = max_chars
    for idx, item in enumerate(results, start=1):
        if remaining <= 0:
            break
        metadata = item.metadata or {}
        answer = metadata.get("answer") or ""
        source = metadata.get("source") or "unknown"
        source_type = metadata.get("source_type") or "question"
        title = metadata.get("title") or ""
        url = metadata.get("url") or ""
        score = f"{item.score:.4f}" if item.score is not None else "n/a"
        text = str(item.text or "")
        text = text[: max(300, remaining)]
        chunk = "\n".join(
            [
                f"[문서 {idx}] type={source_type}, id={item.id}, source={source}, score={score}",
                f"title={title}" if title else "",
                f"url={url}" if url else "",
                text,
                f"정답: {answer}" if answer else "",
            ]
        )
        chunks.append(chunk)
        remaining -= len(chunk)
    return "\n\n".join(chunks)


def build_study_assistant_chain(llm):
    """langchain-kr 튜토리얼처럼 LCEL 파이프(|)로 구성한 RAG 답변 체인."""
    return (
        {
            "question": RunnableLambda(lambda payload: payload["question"]),
            "context": RunnableLambda(lambda payload: format_context(payload["results"], payload.get("max_context_chars", 2400))),
        }
        | STUDY_ASSISTANT_PROMPT
        | llm
        | StrOutputParser()
    )


def build_ollama_llm(model: str, base_url: str, temperature: float = 0.2, num_predict: int = 320):
    try:
        from langchain_community.chat_models import ChatOllama

        try:
            return ChatOllama(model=model, base_url=base_url, temperature=temperature, num_predict=num_predict)
        except TypeError:
            return ChatOllama(model=model, base_url=base_url, temperature=temperature)
    except ImportError:
        from langchain_community.llms import Ollama

        try:
            return Ollama(model=model, base_url=base_url, temperature=temperature, num_predict=num_predict)
        except TypeError:
            return Ollama(model=model, base_url=base_url, temperature=temperature)
