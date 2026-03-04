"""
User service for CRUD operations with Elasticsearch
"""
from datetime import datetime, timezone
from typing import Optional
import logging

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.auth.models import User, UserCreate, UserInDB, OrganizationRole
from backend.auth.security import get_password_hash, verify_password

logger = logging.getLogger("soc-auth")

# Elasticsearch index for users
USERS_INDEX = "soc-users"


class UserService:
    """Service for user management with Elasticsearch storage"""

    def __init__(self):
        self.es = None
        self._initialized = False

    def _get_es(self):
        """Get Elasticsearch client lazily"""
        if self.es is None:
            from elasticsearch import Elasticsearch
            self.es = Elasticsearch(settings.ELASTICSEARCH_HOST)
        # Always ensure index exists (handles case where index was deleted)
        if not self._initialized:
            self._ensure_index()
        return self.es

    def _ensure_index(self):
        """Ensure the users index exists with proper mapping"""
        try:
            if not self.es.indices.exists(index=USERS_INDEX):
                self.es.indices.create(
                    index=USERS_INDEX,
                    body={
                        "mappings": {
                            "properties": {
                                "email": {"type": "keyword"},
                                "username": {"type": "keyword"},
                                "hashed_password": {"type": "keyword"},
                                "created_at": {"type": "date"},
                                "is_active": {"type": "boolean"},
                                "org_id": {"type": "keyword"},
                                "org_role": {"type": "keyword"}
                            }
                        }
                    }
                )
                logger.info(f"Created users index: {USERS_INDEX}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to create users index: {e}")
            self._initialized = False

    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Create a new user"""
        es = self._get_es()

        # Normalize email
        normalized_email = user_data.email.lower().strip()

        # Check if email already exists
        if self.get_user_by_email(normalized_email):
            logger.info(f"User with email {normalized_email} already exists")
            return None

        # Check if username already exists
        if self.get_user_by_username(user_data.username):
            logger.info(f"User with username {user_data.username} already exists")
            return None

        now = datetime.now(timezone.utc)
        user_doc = {
            "email": normalized_email,
            "username": user_data.username,
            "hashed_password": get_password_hash(user_data.password),
            "created_at": now.isoformat(),
            "is_active": True
        }

        try:
            result = es.index(index=USERS_INDEX, document=user_doc, refresh=True)
            user_id = result["_id"]
            logger.info(f"Created user {user_id} with email {normalized_email}")

            return User(
                id=user_id,
                email=normalized_email,
                username=user_data.username,
                created_at=now,
                is_active=True
            )
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get a user by email address"""
        es = self._get_es()
        # Normalize email to lowercase for consistent matching
        email = email.lower().strip()

        try:
            result = es.search(
                index=USERS_INDEX,
                query={"term": {"email": email}},
                size=1
            )

            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                return None

            hit = hits[0]
            source = hit["_source"]

            return UserInDB(
                id=hit["_id"],
                email=source["email"],
                username=source["username"],
                hashed_password=source["hashed_password"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                is_active=source.get("is_active", True),
                org_id=source.get("org_id"),
                org_role=OrganizationRole(source["org_role"]) if source.get("org_role") else None
            )
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """Get a user by username"""
        es = self._get_es()

        try:
            result = es.search(
                index=USERS_INDEX,
                query={"term": {"username": username}},
                size=1
            )

            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                return None

            hit = hits[0]
            source = hit["_source"]

            return UserInDB(
                id=hit["_id"],
                email=source["email"],
                username=source["username"],
                hashed_password=source["hashed_password"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                is_active=source.get("is_active", True),
                org_id=source.get("org_id"),
                org_role=OrganizationRole(source["org_role"]) if source.get("org_role") else None
            )
        except Exception as e:
            logger.error(f"Failed to get user by username: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        es = self._get_es()

        try:
            result = es.get(index=USERS_INDEX, id=user_id)
            source = result["_source"]

            return User(
                id=result["_id"],
                email=source["email"],
                username=source["username"],
                created_at=datetime.fromisoformat(source["created_at"].replace("Z", "+00:00")),
                is_active=source.get("is_active", True),
                org_id=source.get("org_id"),
                org_role=OrganizationRole(source["org_role"]) if source.get("org_role") else None
            )
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password"""
        user = self.get_user_by_email(email)

        if not user:
            logger.warning(f"Authentication failed: user not found for email {email.lower()}")
            return None

        if not verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed: invalid password for email {email.lower()}")
            return None

        if not user.is_active:
            logger.warning(f"Authentication failed: user {email.lower()} is inactive")
            return None

        logger.info(f"User {email.lower()} authenticated successfully")

        # Return User (without hashed_password)
        return User(
            id=user.id,
            email=user.email,
            username=user.username,
            created_at=user.created_at,
            is_active=user.is_active,
            org_id=user.org_id,
            org_role=user.org_role
        )


# Singleton instance
user_service = UserService()
