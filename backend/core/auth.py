import os
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Percorsi esclusi dall'autenticazione
_PUBLIC_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


async def auth_middleware(request: Request, call_next):
    """Verifica il JWT Supabase su tutte le route /api/v1/* tranne quelle pubbliche."""
    path = request.url.path

    # Lascia passare percorsi pubblici e preflight CORS
    if request.method == "OPTIONS" or path in _PUBLIC_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    # Dev locale: se non c'è il secret configurato bypassa l'auth
    if not SUPABASE_JWT_SECRET:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    # Supporto token via query param per CSV export (window.open non invia headers)
    token = request.query_params.get("token") or (
        auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    )

    if not token:
        return JSONResponse({"detail": "Non autenticato"}, status_code=401)

    try:
        jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        return JSONResponse({"detail": "Token scaduto"}, status_code=401)
    except Exception:
        return JSONResponse({"detail": "Token non valido"}, status_code=401)

    return await call_next(request)
