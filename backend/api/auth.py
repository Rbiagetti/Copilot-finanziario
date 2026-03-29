import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

# Configurazione JWT Supabase
JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Verifica il JWT di Supabase fornito nell'header Authorization.
    Restituisce lo user_id (sub) se valido.
    """
    if not JWT_SECRET:
        print("⚠️ [AUTH] SUPABASE_JWT_SECRET non configurata. Accesso libero abilitato.")
        return "anonymous_dev_user"

    token = credentials.credentials
    try:
        # Decodifica il JWT usando il secret di Supabase
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=[ALGORITHM], 
            audience="authenticated" 
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            print("❌ [AUTH] Token decodificato ma 'sub' mancante.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token non valido: user_id mancante",
            )
        
        # Log di successo (minimale per privacy)
        print(f"✅ [AUTH] Utente verificato: {user_id[:8]}...")
        return user_id
        
    except jwt.ExpiredSignatureError:
        print("❌ [AUTH] Token scaduto.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token scaduto",
        )
    except jwt.InvalidTokenError as e:
        print(f"❌ [AUTH] Errore decodifica JWT: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token non valido: {str(e)}",
        )
    except Exception as e:
        print(f"❌ [AUTH] Errore generico Auth: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Errore durante l'autenticazione",
        )
