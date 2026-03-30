import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    if not SUPABASE_URL:
        print("⚠️ [AUTH] SUPABASE_URL non configurata. Accesso libero abilitato.")
        return "anonymous_dev_user"

    token = credentials.credentials
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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")
        
        data = resp.json()
        user_id = data.get("id", "unknown")
        print(f"✅ [AUTH] Utente verificato: {user_id[:8]}...")
        return user_id

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [AUTH] Errore verifica token: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Errore autenticazione")
