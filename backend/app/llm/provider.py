import json
import re

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Providers that support the OpenAI response_format={"type":"json_object"} param.
_JSON_MODE_PROVIDERS = {"groq", "openai"}


def get_llm() -> BaseChatModel:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4.1-mini", api_key=settings.openai_api_key, temperature=0.2)

    if provider == "groq":
        # Groq uses an OpenAI-compatible REST API. Accept either GROQ_API_KEY or GROQ_KEY.
        from langchain_openai import ChatOpenAI

        key = settings.groq_api_key or settings.groq_key
        if not key:
            raise ValueError(
                "LLM_PROVIDER=groq but no key found. Set GROQ_API_KEY or GROQ_KEY."
            )
        return ChatOpenAI(
            model=settings.groq_model,
            api_key=key,
            base_url=_GROQ_BASE_URL,
            temperature=0.2,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.2,
        )

    from langchain_google_vertexai import ChatVertexAI

    return ChatVertexAI(
        model_name=settings.gemini_model,
        project=settings.vertex_project_id,
        location=settings.vertex_location,
        temperature=0.2,
    )


def _sanitize_json_string(text: str) -> str:
    """Escape bare ASCII control characters inside JSON string values.

    Groq (and some other models) occasionally emit literal newline / tab bytes
    inside JSON string values instead of the two-char escape sequences \\n / \\t
    required by the JSON spec.  This state-machine pass fixes them without
    touching structural whitespace outside strings.
    """
    result: list[str] = []
    in_string = False
    i = 0
    _CTRL_ESCAPE = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
    while i < len(text):
        ch = text[i]
        if ch == "\\" and in_string:
            # Already-escaped sequence — copy both chars verbatim.
            result.append(ch)
            i += 1
            if i < len(text):
                result.append(text[i])
        elif ch == '"':
            in_string = not in_string
            result.append(ch)
        elif in_string and ch in _CTRL_ESCAPE:
            result.append(_CTRL_ESCAPE[ch])
        elif in_string and ord(ch) < 0x20:
            # Other bare control chars inside strings: drop them.
            pass
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _robust_parse(content: str) -> dict:
    """Parse JSON from an LLM response with multiple fallback strategies."""
    # Strip markdown code fences if present.
    fenced = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced.strip())

    for candidate in (fenced, content):
        # Attempt 1: direct parse.
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Attempt 2: sanitize control chars, then parse.
        sanitized = _sanitize_json_string(candidate)
        try:
            return json.loads(sanitized)
        except json.JSONDecodeError:
            pass

        # Attempt 3: extract the first {...} block, sanitize, then parse.
        m = re.search(r"\{.*\}", sanitized, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    # All attempts failed — return content as a plain memo.
    return {"memo_markdown": content, "recommendation": "review"}


def generate_structured_report(system_prompt: str, user_prompt: str) -> dict:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    llm = get_llm()

    # Enable JSON mode for providers that support it (Groq, OpenAI).
    # This forces the model to emit syntactically valid JSON, eliminating
    # the most common source of parse failures (bare newlines in strings).
    if provider in _JSON_MODE_PROVIDERS:
        llm = llm.bind(response_format={"type": "json_object"})

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)

    return _robust_parse(content)
