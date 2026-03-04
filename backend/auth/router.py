"""
Authentication API routes
"""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.auth.models import User, UserCreate, UserLogin, Token, OrganizationCreate, OrganizationRole
from backend.auth.security import create_access_token
from backend.auth.user_service import user_service
from backend.auth.dependencies import get_current_user
from backend.auth.organization_service import organization_service

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _check_pending_invitation(email: str) -> bool:
    """Check if there's a pending invitation for this email address."""
    from elasticsearch import Elasticsearch
    from datetime import datetime, timezone

    try:
        es = Elasticsearch(settings.ELASTICSEARCH_HOST)
        if not es.indices.exists(index="soc-org-invitations"):
            return False

        result = es.search(
            index="soc-org-invitations",
            query={
                "bool": {
                    "must": [
                        {"term": {"email": email.lower().strip()}},
                        {"term": {"accepted": False}}
                    ]
                }
            },
            size=1
        )

        hits = result.get("hits", {}).get("hits", [])
        if not hits:
            return False

        # Check if invitation is not expired
        invitation = hits[0]["_source"]
        expires_at = datetime.fromisoformat(invitation["expires_at"].replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < expires_at
    except Exception:
        return False


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user.

    - **email**: Valid email address (must be unique)
    - **username**: Username (3-50 characters, must be unique)
    - **password**: Password (minimum 8 characters)
    """
    # Check if email is already taken
    existing_user = user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username is already taken
    existing_username = user_service.get_user_by_username(user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create the user
    user = user_service.create_user(user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

    # Check if there's a pending invitation for this email
    # If so, skip auto-org creation so they can accept the invite
    has_pending_invitation = _check_pending_invitation(user_data.email)

    if not has_pending_invitation:
        # Auto-create a personal organization for the user
        import re
        slug_base = re.sub(r'[^a-z0-9]', '-', user_data.username.lower())
        slug = f"{slug_base}-workspace"

        # Ensure slug is unique by appending user ID if needed
        if organization_service.get_organization_by_slug(slug):
            slug = f"{slug_base}-{user.id[:8]}"

        org_data = OrganizationCreate(
            name=f"{user_data.username}'s Workspace",
            slug=slug
        )

        org = organization_service.create_organization(org_data, user.id)
        if org:
            # Update user with org info
            organization_service.update_user_org_info(user.id, org.id, OrganizationRole.OWNER)
            # Refresh user to get updated org_id
            user = user_service.get_user_by_id(user.id)

    return user


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    """
    Login with email and password to get an access token.

    Returns a JWT token that should be included in the Authorization header
    for authenticated requests: `Authorization: Bearer <token>`
    """
    user = user_service.authenticate_user(user_data.email, user_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Auto-create organization for existing users without one
    if not user.org_id:
        import re
        slug_base = re.sub(r'[^a-z0-9]', '-', user.username.lower())
        slug = f"{slug_base}-workspace"

        # Ensure slug is unique
        if organization_service.get_organization_by_slug(slug):
            slug = f"{slug_base}-{user.id[:8]}"

        org_data = OrganizationCreate(
            name=f"{user.username}'s Workspace",
            slug=slug
        )

        org = organization_service.create_organization(org_data, user.id)
        if org:
            organization_service.update_user_org_info(user.id, org.id, OrganizationRole.OWNER)
            # Refresh user to get updated org_id
            user = user_service.get_user_by_id(user.id)

    # Create access token with org info
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user.id,
        "email": user.email,
        "org_id": user.org_id,
        "org_role": user.org_role.value if user.org_role else None
    }
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        org_id=user.org_id,
        org_role=user.org_role.value if user.org_role else None
    )


@router.post("/token", response_model=Token)
async def login_for_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 compatible token endpoint.
    Use this endpoint with OAuth2PasswordRequestForm for compatibility with
    Swagger UI's built-in authorization.

    The username field should contain the email address.
    """
    user = user_service.authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Auto-create organization for existing users without one
    if not user.org_id:
        import re
        slug_base = re.sub(r'[^a-z0-9]', '-', user.username.lower())
        slug = f"{slug_base}-workspace"

        if organization_service.get_organization_by_slug(slug):
            slug = f"{slug_base}-{user.id[:8]}"

        org_data = OrganizationCreate(
            name=f"{user.username}'s Workspace",
            slug=slug
        )

        org = organization_service.create_organization(org_data, user.id)
        if org:
            organization_service.update_user_org_info(user.id, org.id, OrganizationRole.OWNER)
            user = user_service.get_user_by_id(user.id)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": user.id,
        "email": user.email,
        "org_id": user.org_id,
        "org_role": user.org_role.value if user.org_role else None
    }
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        org_id=user.org_id,
        org_role=user.org_role.value if user.org_role else None
    )


@router.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.

    Requires a valid JWT token in the Authorization header.
    """
    return current_user
