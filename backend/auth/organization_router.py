"""
Organization API routes for multi-tenancy
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Depends

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from backend.auth.models import (
    Organization, OrganizationCreate, OrganizationMembership,
    OrganizationInvitation, OrganizationRole, InvitationCreate,
    InvitationAccept, MemberUpdate, User, MemberWithUser
)
from backend.auth.user_service import user_service
from backend.auth.organization_service import organization_service
from backend.auth.dependencies import get_current_user, require_org_admin, require_org_membership

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=Organization, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new organization.
    The creating user becomes the owner.
    """
    # Check if user already belongs to an organization
    existing_org = organization_service.get_user_organization(current_user.id)
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization"
        )

    org = organization_service.create_organization(org_data, current_user.id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create organization. Slug may already be taken."
        )

    # Update user with org info
    organization_service.update_user_org_info(
        current_user.id, org.id, OrganizationRole.OWNER
    )

    return org


@router.get("/current", response_model=Organization)
async def get_current_organization(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's organization.
    """
    org = organization_service.get_user_organization(current_user.id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not belong to any organization"
        )
    return org


@router.get("/members", response_model=List[MemberWithUser])
async def get_organization_members(
    current_user: User = Depends(require_org_membership)
):
    """
    Get all members of the current organization with user details.
    Requires membership in the organization.
    """
    membership = organization_service.get_user_membership(current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization"
        )

    members = organization_service.get_organization_members(membership.org_id)

    # Enrich with user details
    members_with_users = []
    for member in members:
        user = user_service.get_user_by_id(member.user_id)
        if user:
            members_with_users.append(MemberWithUser(
                id=member.id,
                user_id=member.user_id,
                org_id=member.org_id,
                role=member.role,
                joined_at=member.joined_at,
                invited_by=member.invited_by,
                email=user.email,
                username=user.username
            ))

    return members_with_users


@router.post("/invite", response_model=OrganizationInvitation, status_code=status.HTTP_201_CREATED)
async def invite_user(
    invitation_data: InvitationCreate,
    current_user: User = Depends(require_org_admin)
):
    """
    Invite a user to the organization.
    Requires ADMIN or OWNER role.
    """
    membership = organization_service.get_user_membership(current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization"
        )

    # Cannot invite with a role higher than your own
    role_hierarchy = {
        OrganizationRole.VIEWER: 0,
        OrganizationRole.ANALYST: 1,
        OrganizationRole.ADMIN: 2,
        OrganizationRole.OWNER: 3
    }
    if role_hierarchy[invitation_data.role] > role_hierarchy[membership.role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite user with a higher role than your own"
        )

    invitation = organization_service.create_invitation(
        org_id=membership.org_id,
        invitation_data=invitation_data,
        invited_by=current_user.id
    )

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create invitation"
        )

    return invitation


@router.post("/invite/{token}/accept", response_model=OrganizationMembership)
async def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user)
):
    """
    Accept an invitation to join an organization.
    """
    # Check if user already belongs to an organization
    existing_org = organization_service.get_user_organization(current_user.id)
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization"
        )

    # Verify invitation email matches user
    invitation = organization_service.get_invitation_by_token(token)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or expired"
        )

    if invitation.email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address"
        )

    membership = organization_service.accept_invitation(token, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to accept invitation. It may be expired or already used."
        )

    # Update user with org info
    organization_service.update_user_org_info(
        current_user.id, membership.org_id, membership.role
    )

    return membership


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: str,
    current_user: User = Depends(require_org_admin)
):
    """
    Remove a member from the organization.
    Requires ADMIN or OWNER role.
    Cannot remove yourself or the last owner.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself. Use leave organization instead."
        )

    membership = organization_service.get_user_membership(current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization"
        )

    # Check the target user's role
    target_membership = organization_service.get_user_membership(user_id)
    if not target_membership or target_membership.org_id != membership.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in organization"
        )

    # Only owners can remove admins
    if target_membership.role == OrganizationRole.ADMIN and membership.role != OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can remove admins"
        )

    # Cannot remove owners unless you are an owner
    if target_membership.role == OrganizationRole.OWNER and membership.role != OrganizationRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can remove other owners"
        )

    success = organization_service.remove_member(membership.org_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove member. Cannot remove the last owner."
        )


@router.patch("/members/{user_id}", response_model=OrganizationMembership)
async def update_member_role(
    user_id: str,
    member_update: MemberUpdate,
    current_user: User = Depends(require_org_admin)
):
    """
    Update a member's role.
    Requires ADMIN or OWNER role.
    """
    membership = organization_service.get_user_membership(current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization"
        )

    # Cannot change your own role
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )

    # Check role hierarchy
    role_hierarchy = {
        OrganizationRole.VIEWER: 0,
        OrganizationRole.ANALYST: 1,
        OrganizationRole.ADMIN: 2,
        OrganizationRole.OWNER: 3
    }

    # Cannot promote to a role higher than your own
    if role_hierarchy[member_update.role] > role_hierarchy[membership.role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign a role higher than your own"
        )

    # Only owners can change owner roles
    target_membership = organization_service.get_user_membership(user_id)
    if target_membership and target_membership.role == OrganizationRole.OWNER:
        if membership.role != OrganizationRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owners can change owner roles"
            )

    updated = organization_service.update_member_role(
        membership.org_id, user_id, member_update.role
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update role. Cannot demote the last owner."
        )

    # Update user document
    organization_service.update_user_org_info(user_id, membership.org_id, member_update.role)

    return updated


@router.get("/invitations", response_model=List[OrganizationInvitation])
async def get_pending_invitations(
    current_user: User = Depends(require_org_admin)
):
    """
    Get all pending invitations for the organization.
    Requires ADMIN or OWNER role.
    """
    membership = organization_service.get_user_membership(current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of any organization"
        )

    return organization_service.get_pending_invitations(membership.org_id)


@router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get organization by ID.
    Only accessible to members of that organization.
    """
    org = organization_service.get_organization_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Verify user is a member
    membership = organization_service.get_user_membership(current_user.id)
    if not membership or membership.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )

    return org
