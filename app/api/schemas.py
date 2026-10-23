from pydantic import BaseModel, Field


class WhoAmIResponse(BaseModel):
    name: str = Field(description="Human-readable API key name.")
    scopes: list[str] = Field(description="Effective scopes granted to the key.")
