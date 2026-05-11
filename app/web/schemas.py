"""Schemas Pydantic para a API web."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    status: str
    is_active: bool


class HuntIn(BaseModel):
    source_input: str = ""
    is_website: bool = False
    manual_niches: list[str] = []
    city: str = ""
    state: str = ""
    country: str = "Brasil"
    max_per_niche: int = 15
    use_ai_qualification: bool = True
    mode: str = "direct_sale"
    selected_products: list[dict] = []
    preloaded_icp: Optional[dict] = None
    preloaded_summary: str = ""


class AnalyzeIn(BaseModel):
    source_input: str
    is_website: bool = False
    force_refresh: bool = False


class LeadUpdateIn(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    observations: Optional[str] = None
    follow_up_text: Optional[str] = None
    campaign_id: Optional[int] = None
    tags: Optional[str] = None
    send_status: Optional[str] = None


class CampaignIn(BaseModel):
    name: str
    description: str = ""
    target_mode: str = "direct_sale"
    color: str = "#6366F1"


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


class SettingsPatch(BaseModel):
    """Patch parcial das configurações globais."""
    ai: Optional[dict] = None
    scraping: Optional[dict] = None
    app: Optional[dict] = None
    messages: Optional[dict] = None
