"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Dict, TypedDict
from uuid import UUID

from app.models.schemas.user import UserResponse


class BusinessHours(TypedDict):
    start: str
    end: str
    enabled: bool


class BusinessHoursDict(TypedDict):
    monday: BusinessHours
    tuesday: BusinessHours
    wednesday: BusinessHours
    thursday: BusinessHours
    friday: BusinessHours
    saturday: BusinessHours
    sunday: BusinessHours


class OrganizationBase(BaseModel):
    name: str
    domain: str
    timezone: Optional[str] = 'UTC'
    business_hours: Optional[BusinessHoursDict] = {
        'monday': {'start': '09:00', 'end': '17:00', 'enabled': True},
        'tuesday': {'start': '09:00', 'end': '17:00', 'enabled': True},
        'wednesday': {'start': '09:00', 'end': '17:00', 'enabled': True},
        'thursday': {'start': '09:00', 'end': '17:00', 'enabled': True},
        'friday': {'start': '09:00', 'end': '17:00', 'enabled': True},
        'saturday': {'start': '09:00', 'end': '17:00', 'enabled': False},
        'sunday': {'start': '09:00', 'end': '17:00', 'enabled': False}
    }
    settings: Optional[Dict] = {}


class OrganizationCreate(OrganizationBase):
    admin_email: EmailStr
    admin_name: str
    admin_password: str

    @field_validator('name', 'admin_name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not 2 <= len(value) <= 100:
            raise ValueError('Must be between 2 and 100 characters')
        return value

    @field_validator('domain')
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or len(value) > 100 or ' ' in value:
            raise ValueError('Enter a valid organization domain')
        return value

    @field_validator('admin_email')
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator('admin_password')
    @classmethod
    def validate_admin_password(cls, value: str) -> str:
        from app.core.security import validate_password_strength
        return validate_password_strength(value)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    timezone: Optional[str] = None
    business_hours: Optional[BusinessHoursDict] = None
    settings: Optional[Dict] = None


class OrganizationCreateResponse(OrganizationBase):
    id: UUID
    is_active: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    user: UserResponse

    class Config:
        from_attributes = True


class OrganizationResponse(OrganizationBase):
    id: UUID
    is_active: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None

