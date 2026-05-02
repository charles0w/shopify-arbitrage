"""
Download supplier images and resize to Shopify-recommended dimensions (2048×2048 max).
Returns list of local file paths.
"""
import os
import uuid
import requests
from pathlib import Path
from PIL import Image
from io import BytesIO

_CACHE_DIR = Path(__file__).parent.parent / "queue" / "images"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_MAX_DIM = 2048
_TIMEOUT = 15


def download_images(image_urls: list[str], max_images: int = 5) -> list[str]:
    """Download up to max_images URLs. Returns local paths of successfully saved images."""
    paths = []
    for url in image_urls[:max_images]:
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=_TIMEOUT, stream=True)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            img.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)
            fname = _CACHE_DIR / f"{uuid.uuid4().hex}.jpg"
            img.save(fname, "JPEG", quality=88, optimize=True)
            paths.append(str(fname))
        except Exception:
            continue
    return paths
