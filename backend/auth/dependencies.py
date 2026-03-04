"""
FastAPI dependencies for authentication and multi-tenancy
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Query, Request

from fastapi.security import OAuth2PasswordBearer

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.auth.models import User, TokenData, OrganizationRole
from backend.auth.security import decode_token
from backend.auth.user_service import user_service
from backend.models.schemas import TenantContext

# OAuth2 scheme for token extraction from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    Raises 401 if token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = user_service.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    return user


async def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[User]:
    """
    Optional version - returns None if not authenticated instead of raising exception.
    Useful for routes that have different behavior for authenticated vs anonymous users.
    """
    if not token:
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    user_id: str = payload.get("sub")
    if user_id is None:
        return None

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        return None

    return user


def get_token_from_query(token: Optional[str] = Query(None, alias="token")) -> Optional[str]:
    """Extract token from query parameter (for WebSocket connections)"""
    return token


async def get_current_user_ws(token: Optional[str] = Depends(get_token_from_query)) -> Optional[User]:
    """
    Get current user from WebSocket query parameter.
    WebSockets can't use Authorization header, so we use query param.
    """
    if not token:
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    user_id: str = payload.get("sub")
    if user_id is None:
        return None

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        return None

    return user


async def get_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> TenantContext:
    """
    Extract tenant context from the authenticated user.
    Raises 403 if user has no organization.
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization to access this resource"
        )

    # Get organization details for the slug
    from backend.auth.organization_service import organization_service
    org = organization_service.get_organization_by_id(current_user.org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found"
        )

    return TenantContext(
        org_id=current_user.org_id,
        org_slug=org.slug,
        user_id=current_user.id,
        user_role=current_user.org_role.value if current_user.org_role else "VIEWER"
    )


async def get_tenant_context_optional(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Optional[TenantContext]:
    """
    Optional version of get_tenant_context.
    Returns None if user is not authenticated or has no organization.
    """
    if not current_user or not current_user.org_id:
        return None

    from backend.auth.organization_service import organization_service
    org = organization_service.get_organization_by_id(current_user.org_id)

    if not org:
        return None

    return TenantContext(
        org_id=current_user.org_id,
        org_slug=org.slug,
        user_id=current_user.id,
        user_role=current_user.org_role.value if current_user.org_role else "VIEWER"
    )


async def require_org_membership(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be a member of an organization.
    Returns the user if they are a member.
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization"
        )
    return current_user


async def require_org_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to have ADMIN or OWNER role in their organization.
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization"
        )

    if current_user.org_role not in [OrganizationRole.ADMIN, OrganizationRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required"
        )

    return current_user


async def require_org_analyst(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to have ANALYST, ADMIN, or OWNER role.
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization"
        )

    if current_user.org_role not in [
        OrganizationRole.ANALYST,
        OrganizationRole.ADMIN,
        OrganizationRole.OWNER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst role or higher required"
        )

    return current_user


async def require_org_owner(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to have OWNER role in their organization.
    """
    if not current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization"
        )

    if current_user.org_role != OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required"
        )

    return current_user
