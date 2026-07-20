"""Tunn klient mot lokal Ollama.

Abstraktionspunkten för AI: vill man senare koppla in ett moln-API som
fallback är det denna modul som byts ut/utökas — resten av appen anropar
bara `chat()`.
"""

import httpx

from app.config import get_settings


class AIUnavailable(Exception):
    """Ollama svarar inte eller gav oanvändbart svar."""


# Under Cloudflares ~100 s-gräns: hellre vårt eget svenska felmeddelande
# än en rå 502 från tunneln när modellen är långsam/kall.
DEFAULT_TIMEOUT = 90.0


async def warm() -> None:
    """Förladda modellerna i Ollama (tomt meddelande = bara load).

    Körs i bakgrunden vid API-start så första riktiga anropet slipper
    betala uppvärmningen — och keep_alive håller dem sedan i minnet."""
    settings = get_settings()
    for model in (settings.ollama_text_model, settings.ollama_vision_model):
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={"model": model, "messages": [], "keep_alive": "2h"},
                )
        except httpx.HTTPError:
            pass  # Ollama nere — värms istället vid första anropet


async def chat(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    images_b64: list[str] | None = None,
    json_format: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    max_tokens: int | None = None,
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

    # keep_alive: håll modellen i minnet efter användning — annars lastas
    # den ur efter 5 min och nästa anrop får betala uppvärmningen igen.
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": "2h",
    }
    if json_format:
        payload["format"] = "json"
    if max_tokens:
        # Kapa svarslängden — vision-svar utan tak kan mala i onödan
        payload["options"] = {"num_predict": max_tokens}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/chat", json=payload
            )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except (httpx.HTTPError, KeyError) as exc:
        raise AIUnavailable(f"Ollama otillgänglig: {exc}") from exc
