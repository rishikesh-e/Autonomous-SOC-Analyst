"""
Organization service for CRUD operations with Elasticsearch
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import logging
import uuid
import secrets

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.auth.models import (
    Organization, OrganizationCreate, OrganizationInDB,
    OrganizationMembership, OrganizationInvitation, OrganizationRole,
    OrganizationSettings, User, InvitationCreate
)

logger = logging.getLogger("soc-auth")

# Elasticsearch indices for organizations
ORGANIZATIONS_INDEX = "soc-organizations"
MEMBERSHIPS_INDEX = "soc-org-memberships"
INVITATIONS_INDEX = "soc-org-invitations"


class OrganizationService:
    """Service for organization management with Elasticsearch storage"""

    def __init__(self):
        self.es = None
        self._initialized = False

    def _get_es(self):
        """Get Elasticsearch client lazily"""
        if self.es is None:
            from elasticsearch import Elasticsearch
            self.es = Elasticsearch(settings.ELASTICSEARCH_HOST)
        # Always ensure indices exist (handles case where indices were deleted)
        if not self._initialized:
            self._ensure_indices()
        return self.es

    def _ensure_indices(self):
        """Ensure all organization-related indices exist"""
        if self._initialized:
            return

        indices_config = {
            ORGANIZATIONS_INDEX: {
                "mappings": {
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "slug": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},
                        "is_active": {"type": "boolean"},
                        "settings": {"type": "object"}
                    }
                }
            },
            MEMBERSHIPS_INDEX: {
                "mappings": {
                    "properties": {
                        "user_id": {"type": "keyword"},
                        "org_id": {"type": "keyword"},
                        "role": {"type": "keyword"},
                        "joined_at": {"type": "date"},
                        "invited_by": {"type": "keyword"}
                    }
                }
            },
            INVITATIONS_INDEX: {
                "mappings": {
                    "properties": {
                        "org_id": {"type": "keyword"},
                        "email": {"type": "keyword"},
                        "role": {"type": "keyword"},
                        "token": {"type": "keyword"},
                        "created_at": {"type": "date"},
                        "expires_at": {"type": "date"},
                        "invited_by": {"type": "keyword"},
                        "accepted": {"type": "boolean"},
                        "accepted_at": {"type": "date"}
                    }
                }
            }
        }

        try:
            for index_name, config in indices_config.items():
                if not self.es.indices.exists(index=index_name):
                    self.es.indices.create(index=index_name, body=config)
                    logger.info(f"Created index: {index_name}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to create organization indices: {e}")
            self._initialized = False

    def create_organization(
        self,
        org_data: OrganizationCreate,
        creator_user_id: str
    ) -> Optional[Organization]:
        """Create a new organization and set creator as owner"""
        es = self._get_es()

        # Check if slug already exists
        if self.get_organization_by_slug(org_data.slug):
            logger.warning(f"Organization slug already exists: {org_data.slug}")
            return None

        now = datetime.now(timezone.utc)
        org_id = str(uuid.uuid4())

        org_doc = {
            "name": org_data.name,
            "slug": org_data.slug,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_active": True,
            "settings": (org_data.settings or OrganizationSettings()).model_dump()
        }

        try:
            # Create the organization
            es.index(index=ORGANIZATIONS_INDEX, id=org_id, document=org_doc, refresh=True)

            # Add creator as owner
            self._create_membership(
                user_id=creator_user_id,
                org_id=org_id,
                role=OrganizationRole.OWNER,
                invited_by=None
            )

            return Organization(
                id=org_id,
                name=org_data.name,
                slug=org_data.slug,
                created_at=now,
                updated_at=now,
                settings=org_data.settings or OrganizationSettings(),
                is_active=True
            )
        except Exception as e:
            logger.error(f"Failed to create organization: {e}")
            return None

    def get_organization_by_id(self, org_id: str) -> Optional[Organization]:
        """Get organization by ID"""
        es = self._get_es()

        try:
            result = es.get(index=ORGANIZATIONS_INDEX, id=org_id)
            source = result["_source"]

            return Organization(
                id=result["_id"],
                name=source["name"],
                slug=source["slug"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(source["updated_at"].replace("Z", "+00:00")),
                settings=OrganizationSettings(**source.get("settings", {})),
                is_active=source.get("is_active", True)
            )
        except Exception as e:
            logger.debug(f"Organization not found by ID: {org_id}")
            return None

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by slug"""
        es = self._get_es()

        try:
            result = es.search(
                index=ORGANIZATIONS_INDEX,
                query={"term": {"slug": slug}},
                size=1
            )

            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                return None

            hit = hits[0]
            source = hit["_source"]

            return Organization(
                id=hit["_id"],
                name=source["name"],
                slug=source["slug"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(source["updated_at"].replace("Z", "+00:00")),
                settings=OrganizationSettings(**source.get("settings", {})),
                is_active=source.get("is_active", True)
            )
        except Exception as e:
            logger.error(f"Failed to get organization by slug: {e}")
            return None

    def get_user_organization(self, user_id: str) -> Optional[Organization]:
        """Get the organization a user belongs to"""
        membership = self.get_user_membership(user_id)
        if not membership:
            return None
        return self.get_organization_by_id(membership.org_id)

    def get_user_membership(self, user_id: str) -> Optional[OrganizationMembership]:
        """Get user's organization membership"""
        es = self._get_es()

        try:
            result = es.search(
                index=MEMBERSHIPS_INDEX,
                query={"term": {"user_id": user_id}},
                size=1
            )

            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                return None

            hit = hits[0]
            source = hit["_source"]

            return OrganizationMembership(
                id=hit["_id"],
                user_id=source["user_id"],
                org_id=source["org_id"],
                role=OrganizationRole(source["role"]),
                joined_at=datetime.fromisoformat(source["joined_at"].replace("Z", "+00:00")),
                invited_by=source.get("invited_by")
            )
        except Exception as e:
            logger.error(f"Failed to get user membership: {e}")
            return None

    def _create_membership(
        self,
        user_id: str,
        org_id: str,
        role: OrganizationRole,
        invited_by: Optional[str]
    ) -> Optional[OrganizationMembership]:
        """Create a membership record"""
        es = self._get_es()

        now = datetime.now(timezone.utc)
        membership_id = str(uuid.uuid4())

        membership_doc = {
            "user_id": user_id,
            "org_id": org_id,
            "role": role.value,
            "joined_at": now.isoformat(),
            "invited_by": invited_by
        }

        try:
            es.index(index=MEMBERSHIPS_INDEX, id=membership_id, document=membership_doc, refresh=True)

            return OrganizationMembership(
                id=membership_id,
                user_id=user_id,
                org_id=org_id,
                role=role,
                joined_at=now,
                invited_by=invited_by
            )
        except Exception as e:
            logger.error(f"Failed to create membership: {e}")
            return None

    def get_organization_members(self, org_id: str) -> List[OrganizationMembership]:
        """Get all members of an organization"""
        es = self._get_es()

        try:
            result = es.search(
                index=MEMBERSHIPS_INDEX,
                query={"term": {"org_id": org_id}},
                size=1000
            )

            members = []
            for hit in result.get("hits", {}).get("hits", []):
                source = hit["_source"]
                members.append(OrganizationMembership(
                    id=hit["_id"],
                    user_id=source["user_id"],
                    org_id=source["org_id"],
                    role=OrganizationRole(source["role"]),
                    joined_at=datetime.fromisoformat(source["joined_at"].replace("Z", "+00:00")),
                    invited_by=source.get("invited_by")
                ))
            return members
        except Exception as e:
            logger.error(f"Failed to get organization members: {e}")
            return []

    def add_member(
        self,
        org_id: str,
        user_id: str,
        role: OrganizationRole,
        invited_by: str
    ) -> Optional[OrganizationMembership]:
        """Add a user as a member of an organization"""
        # Check if already a member
        existing = self.get_user_membership(user_id)
        if existing:
            logger.warning(f"User {user_id} is already a member of an organization")
            return None

        return self._create_membership(user_id, org_id, role, invited_by)

    def remove_member(self, org_id: str, user_id: str) -> bool:
        """Remove a member from an organization"""
        es = self._get_es()

        membership = self.get_user_membership(user_id)
        if not membership or membership.org_id != org_id:
            return False

        # Prevent removing the last owner
        if membership.role == OrganizationRole.OWNER:
            members = self.get_organization_members(org_id)
            owners = [m for m in members if m.role == OrganizationRole.OWNER]
            if len(owners) <= 1:
                logger.warning("Cannot remove the last owner from organization")
                return False

        try:
            es.delete(index=MEMBERSHIPS_INDEX, id=membership.id, refresh=True)
            return True
        except Exception as e:
            logger.error(f"Failed to remove member: {e}")
            return False

    def update_member_role(
        self,
        org_id: str,
        user_id: str,
        new_role: OrganizationRole
    ) -> Optional[OrganizationMembership]:
        """Update a member's role"""
        es = self._get_es()

        membership = self.get_user_membership(user_id)
        if not membership or membership.org_id != org_id:
            return None

        # Prevent demoting the last owner
        if membership.role == OrganizationRole.OWNER and new_role != OrganizationRole.OWNER:
            members = self.get_organization_members(org_id)
            owners = [m for m in members if m.role == OrganizationRole.OWNER]
            if len(owners) <= 1:
                logger.warning("Cannot demote the last owner")
                return None

        try:
            es.update(
                index=MEMBERSHIPS_INDEX,
                id=membership.id,
                doc={"role": new_role.value},
                refresh=True
            )

            membership.role = new_role
            return membership
        except Exception as e:
            logger.error(f"Failed to update member role: {e}")
            return None

    def create_invitation(
        self,
        org_id: str,
        invitation_data: InvitationCreate,
        invited_by: str
    ) -> Optional[OrganizationInvitation]:
        """Create an invitation to join an organization"""
        es = self._get_es()

        now = datetime.now(timezone.utc)
        invitation_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)

        invitation_doc = {
            "org_id": org_id,
            "email": invitation_data.email,
            "role": invitation_data.role.value,
            "token": token,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=7)).isoformat(),
            "invited_by": invited_by,
            "accepted": False,
            "accepted_at": None
        }

        try:
            es.index(index=INVITATIONS_INDEX, id=invitation_id, document=invitation_doc, refresh=True)

            return OrganizationInvitation(
                id=invitation_id,
                org_id=org_id,
                email=invitation_data.email,
                role=invitation_data.role,
                token=token,
                created_at=now,
                expires_at=now + timedelta(days=7),
                invited_by=invited_by,
                accepted=False
            )
        except Exception as e:
            logger.error(f"Failed to create invitation: {e}")
            return None

    def get_invitation_by_token(self, token: str) -> Optional[OrganizationInvitation]:
        """Get an invitation by its token"""
        es = self._get_es()

        try:
            result = es.search(
                index=INVITATIONS_INDEX,
                query={"term": {"token": token}},
                size=1
            )

            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                return None

            hit = hits[0]
            source = hit["_source"]

            return OrganizationInvitation(
                id=hit["_id"],
                org_id=source["org_id"],
                email=source["email"],
                role=OrganizationRole(source["role"]),
                token=source["token"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                expires_at=datetime.fromisoformat(source["expires_at"].replace("Z", "+00:00")),
                invited_by=source["invited_by"],
                accepted=source.get("accepted", False),
                accepted_at=datetime.fromisoformat(source["accepted_at"].replace("Z", "+00:00")) if source.get("accepted_at") else None
            )
        except Exception as e:
            logger.error(f"Failed to get invitation by token: {e}")
            return None

    def accept_invitation(
        self,
        token: str,
        user_id: str
    ) -> Optional[OrganizationMembership]:
        """Accept an invitation and create membership"""
        es = self._get_es()

        invitation = self.get_invitation_by_token(token)
        if not invitation:
            logger.warning("Invitation not found")
            return None

        if invitation.accepted:
            logger.warning("Invitation already accepted")
            return None

        if datetime.now(timezone.utc) > invitation.expires_at:
            logger.warning("Invitation has expired")
            return None

        # Create membership
        membership = self.add_member(
            org_id=invitation.org_id,
            user_id=user_id,
            role=invitation.role,
            invited_by=invitation.invited_by
        )

        if not membership:
            return None

        # Mark invitation as accepted
        try:
            es.update(
                index=INVITATIONS_INDEX,
                id=invitation.id,
                doc={
                    "accepted": True,
                    "accepted_at": datetime.now(timezone.utc).isoformat()
                },
                refresh=True
            )
        except Exception as e:
            logger.error(f"Failed to mark invitation as accepted: {e}")

        return membership

    def get_pending_invitations(self, org_id: str) -> List[OrganizationInvitation]:
        """Get all pending invitations for an organization"""
        es = self._get_es()

        try:
            result = es.search(
                index=INVITATIONS_INDEX,
                query={
                    "bool": {
                        "must": [
                            {"term": {"org_id": org_id}},
                            {"term": {"accepted": False}}
                        ]
                    }
                },
                size=100
            )

            invitations = []
            for hit in result.get("hits", {}).get("hits", []):
                source = hit["_source"]
                invitations.append(OrganizationInvitation(
                    id=hit["_id"],
                    org_id=source["org_id"],
                    email=source["email"],
                    role=OrganizationRole(source["role"]),
                    token=source["token"],
                    created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                    expires_at=datetime.fromisoformat(source["expires_at"].replace("Z", "+00:00")),
                    invited_by=source["invited_by"],
                    accepted=False
                ))
            return invitations
        except Exception as e:
            logger.error(f"Failed to get pending invitations: {e}")
            return []

    def update_organization(
        self,
        org_id: str,
        updates: dict
    ) -> Optional[Organization]:
        """Update organization details"""
        es = self._get_es()

        try:
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            es.update(
                index=ORGANIZATIONS_INDEX,
                id=org_id,
                doc=updates,
                refresh=True
            )
            return self.get_organization_by_id(org_id)
        except Exception as e:
            logger.error(f"Failed to update organization: {e}")
            return None

    def update_user_org_info(self, user_id: str, org_id: str, role: OrganizationRole) -> bool:
        """Update user document with organization info"""
        from backend.auth.user_service import USERS_INDEX
        es = self._get_es()

        try:
            es.update(
                index=USERS_INDEX,
                id=user_id,
                doc={
                    "org_id": org_id,
                    "org_role": role.value
                },
                refresh=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update user org info: {e}")
            return False


# Singleton instance
organization_service = OrganizationService()
