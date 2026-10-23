from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_current_api_key
from app.api.schemas import WhoAmIResponse
from app.core.security import effective_scopes
from app.db.models import ApiKey

router = APIRouter(tags=["auth"])


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(
    key: Annotated[ApiKey, Depends(get_current_api_key)],
) -> WhoAmIResponse:
    """Return the name and effective scopes of the presented API key."""
    return WhoAmIResponse(
        name=key.name,
        scopes=[scope.value for scope in effective_scopes(key.scope)],
    )
