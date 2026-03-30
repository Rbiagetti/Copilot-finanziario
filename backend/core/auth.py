import os
import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_PUBLIC_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if request.method == "OPTIONS" or path in _PUBLIC_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    if not SUPABASE_URL:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    token = request.query_params.get("token") or (
        auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    )

    if not token:
        return JSONResponse({"detail": "Non autenticato"}, status_code=401)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_ANON_KEY,
                },
                timeout=5.0,
            )
        if resp.status_code != 200:
            return JSONResponse({"detail": "Token non valido"}, status_code=401)
    except Exception as e:
        print(f"❌ [AUTH] Errore verifica token: {e}")
        return JSONResponse({"detail": "Errore autenticazione"}, status_code=500)

    return await call_next(request)
