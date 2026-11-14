"""Supabase Storage access for uploaded originals.

Objects are private. The API reads and writes them with the service role; the
bucket RLS policies scope paths to organisation members for any direct client.
Originals are never rendered inline: the download route always sends an
attachment and only ever a PDF or plain-text content type.
"""

from __future__ import annotations

import httpx

from .config import Settings


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }


def configured(settings: Settings) -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def _url(settings: Settings, path: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/documents/{path}"


async def put(settings: Settings, path: str, data: bytes, content_type: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            _url(settings, path),
            headers={
                **_headers(settings),
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=data,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"storage upload failed ({response.status_code})")


async def get(settings: Settings, path: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(_url(settings, path), headers=_headers(settings))
    if response.status_code == 404:
        raise FileNotFoundError(path)
    if response.status_code >= 400:
        raise RuntimeError(f"storage read failed ({response.status_code})")
    return response.content


async def delete(settings: Settings, path: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(_url(settings, path), headers=_headers(settings))
    if response.status_code >= 400 and response.status_code != 404:
        raise RuntimeError(f"storage delete failed ({response.status_code})")
