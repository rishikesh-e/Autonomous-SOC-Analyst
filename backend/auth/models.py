"""
Pydantic models for user authentication and organization multi-tenancy
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, EmailStr, Field
import uuid


class OrganizationRole(str, Enum):
    """Roles within an organization"""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class OrganizationSettings(BaseModel):
    """Organization-specific settings"""
    max_users: int = 100
    log_retention_days: int = 90
    auto_approve_enabled: bool = True
    autonomous_mode: bool = True
    alert_email: Optional[str] = None
    slack_webhook: Optional[str] = None


class OrganizationBase(BaseModel):
    """Base organization model"""
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=50, pattern=r'^[a-z0-9-]+$')


class OrganizationCreate(OrganizationBase):
    """Model for creating an organization"""
    settings: Optional[OrganizationSettings] = None


class Organization(OrganizationBase):
    """Organization model returned by API"""
    id: str
    created_at: datetime
    updated_at: datetime
    settings: OrganizationSettings = Field(default_factory=OrganizationSettings)
    is_active: bool = True

    class Config:
        from_attributes = True


class OrganizationInDB(Organization):
    """Organization model as stored in database"""
    pass


class OrganizationMembership(BaseModel):
    """Links users to organizations with roles"""
    id: str
    user_id: str
    org_id: str
    role: OrganizationRole
    joined_at: datetime
    invited_by: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationInvitation(BaseModel):
    """Invitation to join an organization"""
    id: str
    org_id: str
    email: EmailStr
    role: OrganizationRole = OrganizationRole.ANALYST
    token: str
    created_at: datetime
    expires_at: datetime
    invited_by: str
    accepted: bool = False
    accepted_at: Optional[datetime] = None


class UserBase(BaseModel):
    """Base user model with common fields"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """Model for user registration"""
    password: str = Field(..., min_length=8)
    org_name: Optional[str] = None  # If provided, creates org and sets user as owner


class UserLogin(BaseModel):
    """Model for user login"""
    email: EmailStr
    password: str


class User(UserBase):
    """User model returned by the API (excludes password)"""
    id: str
    created_at: datetime
    is_active: bool = True
    org_id: Optional[str] = None
    org_role: Optional[OrganizationRole] = None

    class Config:
        from_attributes = True


class UserInDB(User):
    """User model stored in database (includes hashed password)"""
    hashed_password: str


class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str = "bearer"
    org_id: Optional[str] = None
    org_role: Optional[str] = None


class TokenData(BaseModel):
    """Data encoded in the JWT token"""
    user_id: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[str] = None
    org_role: Optional[str] = None


class InvitationAccept(BaseModel):
    """Model for accepting an invitation"""
    password: str = Field(..., min_length=8)
    username: str = Field(..., min_length=3, max_length=50)


class MemberUpdate(BaseModel):
    """Model for updating a member's role"""
    role: OrganizationRole


class InvitationCreate(BaseModel):
    """Model for creating an invitation"""
    email: EmailStr
    role: OrganizationRole = OrganizationRole.ANALYST


class MemberWithUser(BaseModel):
    """Organization membership with user details"""
    id: str
    user_id: str
    org_id: str
    role: OrganizationRole
    joined_at: datetime
    invited_by: Optional[str] = None
    email: str
    username: str

    class Config:
        from_attributes = True
