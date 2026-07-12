"""Tunn klient mot lokal Ollama.

Abstraktionspunkten för AI: vill man senare koppla in ett moln-API som
fallback är det denna modul som byts ut/utökas — resten av appen anropar
bara `chat()`.
"""

import httpx

from app.config import get_settings


class AIUnavailable(Exception):
    """Ollama svarar inte eller gav oanvändbart svar."""


async def chat(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    images_b64: list[str] | None = None,
    json_format: bool = False,
    timeout: float = 120.0,
) -> str:
    settings = get_settings()
    model = model or (
        settings.ollama_vision_model if images_b64 else settings.ollama_text_model
    )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user_msg: dict = {"role": "user", "content": prompt}
    if images_b64:
        user_msg["images"] = images_b64
    messages.append(user_msg)

    payload: dict = {"model": model, "messages": messages, "stream": False}
    if json_format:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/chat", json=payload
            )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except (httpx.HTTPError, KeyError) as exc:
        raise AIUnavailable(f"Ollama otillgänglig: {exc}") from exc
