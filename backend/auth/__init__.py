"""
Authentication module for the SOC Analyst API
"""
from backend.auth.router import router as auth_router
from backend.auth.organization_router import router as org_router
from backend.auth.dependencies import (
    get_current_user,
    get_tenant_context,
    require_org_admin,
    require_org_analyst,
    require_org_membership
)
from backend.auth.models import (
    User, UserCreate, UserLogin, Token,
    Organization, OrganizationCreate, OrganizationRole,
    OrganizationMembership, OrganizationInvitation
)

__all__ = [
    "auth_router",
    "org_router",
    "get_current_user",
    "get_tenant_context",
    "require_org_admin",
    "require_org_analyst",
    "require_org_membership",
    "User",
    "UserCreate",
    "UserLogin",
    "Token",
    "Organization",
    "OrganizationCreate",
    "OrganizationRole",
    "OrganizationMembership",
    "OrganizationInvitation"
]
