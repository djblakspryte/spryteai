from __future__ import annotations

import os

import aiohttp

ATTRIBUTES_THRESHOLDS = {
    "INSULT": 0.75,
    "TOXICITY": 0.75,
    "SPAM": 0.75,
}


async def perspective_api(chat_data: str) -> dict[str, bool]:
    """Analyze text with Google's Perspective API without blocking the Discord event loop."""
    api_key = os.getenv("PERSPECTIVE_API_KEY")
    if not api_key:
        raise RuntimeError("PERSPECTIVE_API_KEY is not configured")

    payload = {
        "comment": {"text": chat_data},
        "requestedAttributes": {key: {} for key in ATTRIBUTES_THRESHOLDS},
    }
    url = "https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, params={"key": api_key}, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

    return {
        key: data["attributeScores"][key]["summaryScore"]["value"] > threshold
        for key, threshold in ATTRIBUTES_THRESHOLDS.items()
    }
