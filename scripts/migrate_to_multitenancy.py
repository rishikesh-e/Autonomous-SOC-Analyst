#!/usr/bin/env python3
"""
Migration Script: Convert existing data to multi-tenant structure

This script:
1. Creates a default organization
2. Assigns all existing users to the default organization
3. Reindexes existing data into tenant-scoped indices
4. Optionally deletes the old indices

Usage:
    python scripts/migrate_to_multitenancy.py --dry-run          # Preview changes
    python scripts/migrate_to_multitenancy.py                    # Execute migration
    python scripts/migrate_to_multitenancy.py --delete-old       # Execute and delete old indices
"""
import argparse
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from elasticsearch import Elasticsearch
from elasticsearch.helpers import reindex, bulk

from config.settings import settings


class MultiTenancyMigration:
    """Handles migration to multi-tenant architecture"""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.es = Elasticsearch(hosts=[settings.ELASTICSEARCH_HOST])

        # Index names
        self.old_indices = {
            "users": "soc-users",
            "logs": "soc-logs",
            "logs_pattern": "soc-logs*",
            "anomalies": "soc-anomalies",
            "incidents": "soc-incidents",
        }

        # New index configurations for default org
        self.default_org_id = None
        self.default_org_slug = "default"

        # Statistics
        self.stats = {
            "users_updated": 0,
            "logs_migrated": 0,
            "anomalies_migrated": 0,
            "incidents_migrated": 0,
            "errors": []
        }

    def run(self, delete_old: bool = False) -> Dict[str, Any]:
        """Execute the full migration"""
        print("=" * 60)
        print("Multi-Tenancy Migration")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Delete old indices after migration: {delete_old}")
        print()

        # Step 1: Create default organization
        print("[1/5] Creating default organization...")
        self._create_default_organization()

        # Step 2: Update all users with org info
        print("\n[2/5] Updating existing users...")
        self._update_users()

        # Step 3: Migrate logs
        print("\n[3/5] Migrating logs...")
        self._migrate_logs()

        # Step 4: Migrate anomalies
        print("\n[4/5] Migrating anomalies...")
        self._migrate_anomalies()

        # Step 5: Migrate incidents
        print("\n[5/5] Migrating incidents...")
        self._migrate_incidents()

        # Optional: Delete old indices
        if delete_old and not self.dry_run:
            print("\n[6/6] Deleting old indices...")
            self._delete_old_indices()

        # Print summary
        self._print_summary()

        return self.stats

    def _create_default_organization(self):
        """Create the default organization"""
        self.default_org_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        org_doc = {
            "name": "Default Organization",
            "slug": self.default_org_slug,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "is_active": True,
            "settings": {
                "max_users": 1000,
                "log_retention_days": 90,
                "auto_approve_enabled": True,
                "autonomous_mode": True
            }
        }

        if self.dry_run:
            print(f"  [DRY RUN] Would create organization: {self.default_org_slug} ({self.default_org_id})")
        else:
            try:
                # Check if organizations index exists
                if not self.es.indices.exists(index="soc-organizations"):
                    self.es.indices.create(
                        index="soc-organizations",
                        body={
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
                        }
                    )

                # Check if default org already exists
                result = self.es.search(
                    index="soc-organizations",
                    query={"term": {"slug": self.default_org_slug}},
                    size=1
                )
                hits = result.get("hits", {}).get("hits", [])
                if hits:
                    self.default_org_id = hits[0]["_id"]
                    print(f"  Default organization already exists: {self.default_org_id}")
                else:
                    self.es.index(
                        index="soc-organizations",
                        id=self.default_org_id,
                        document=org_doc,
                        refresh=True
                    )
                    print(f"  Created default organization: {self.default_org_id}")

            except Exception as e:
                self.stats["errors"].append(f"Failed to create organization: {e}")
                print(f"  ERROR: {e}")

    def _update_users(self):
        """Update all existing users with organization info"""
        if not self.es.indices.exists(index=self.old_indices["users"]):
            print("  No users index found, skipping...")
            return

        try:
            # Get all users
            result = self.es.search(
                index=self.old_indices["users"],
                query={"match_all": {}},
                size=10000
            )

            users = result.get("hits", {}).get("hits", [])
            print(f"  Found {len(users)} users to update")

            for hit in users:
                user_id = hit["_id"]
                source = hit["_source"]

                # Skip if already has org_id
                if source.get("org_id"):
                    continue

                if self.dry_run:
                    print(f"  [DRY RUN] Would update user {user_id} ({source.get('email', 'unknown')})")
                else:
                    try:
                        self.es.update(
                            index=self.old_indices["users"],
                            id=user_id,
                            doc={
                                "org_id": self.default_org_id,
                                "org_role": "OWNER"  # Make first users owners
                            },
                            refresh=True
                        )
                        self.stats["users_updated"] += 1
                    except Exception as e:
                        self.stats["errors"].append(f"Failed to update user {user_id}: {e}")

            # Also create membership records
            self._create_memberships(users)

        except Exception as e:
            self.stats["errors"].append(f"Failed to update users: {e}")
            print(f"  ERROR: {e}")

    def _create_memberships(self, users: List[Dict]):
        """Create membership records for migrated users"""
        if not users:
            return

        memberships_index = "soc-org-memberships"

        if not self.dry_run:
            # Ensure memberships index exists
            if not self.es.indices.exists(index=memberships_index):
                self.es.indices.create(
                    index=memberships_index,
                    body={
                        "mappings": {
                            "properties": {
                                "user_id": {"type": "keyword"},
                                "org_id": {"type": "keyword"},
                                "role": {"type": "keyword"},
                                "joined_at": {"type": "date"},
                                "invited_by": {"type": "keyword"}
                            }
                        }
                    }
                )

        now = datetime.now(timezone.utc)

        for i, hit in enumerate(users):
            user_id = hit["_id"]
            source = hit["_source"]

            # Skip if already has org_id
            if source.get("org_id"):
                continue

            membership_doc = {
                "user_id": user_id,
                "org_id": self.default_org_id,
                "role": "OWNER" if i == 0 else "ANALYST",  # First user is owner
                "joined_at": now.isoformat(),
                "invited_by": None
            }

            if self.dry_run:
                print(f"  [DRY RUN] Would create membership for user {user_id}")
            else:
                try:
                    self.es.index(
                        index=memberships_index,
                        document=membership_doc,
                        refresh=True
                    )
                except Exception as e:
                    self.stats["errors"].append(f"Failed to create membership for {user_id}: {e}")

    def _migrate_logs(self):
        """Migrate logs to tenant-scoped index"""
        new_logs_index = f"soc-logs-{self.default_org_id}"

        # Count existing logs
        try:
            count_result = self.es.count(index=self.old_indices["logs_pattern"])
            total_logs = count_result.get("count", 0)
            print(f"  Found {total_logs} logs to migrate")
        except Exception as e:
            print(f"  No logs found or error counting: {e}")
            return

        if total_logs == 0:
            return

        if self.dry_run:
            print(f"  [DRY RUN] Would migrate {total_logs} logs to {new_logs_index}")
        else:
            try:
                # Create new index with same mappings
                if not self.es.indices.exists(index=new_logs_index):
                    # Get mapping from old index
                    old_mapping = self.es.indices.get_mapping(index=self.old_indices["logs"])
                    first_index = list(old_mapping.keys())[0]
                    mappings = old_mapping[first_index].get("mappings", {})

                    self.es.indices.create(
                        index=new_logs_index,
                        mappings=mappings
                    )

                # Reindex with scroll
                result = reindex(
                    self.es,
                    source_index=self.old_indices["logs_pattern"],
                    target_index=new_logs_index
                )
                self.stats["logs_migrated"] = result[0]
                print(f"  Migrated {result[0]} logs")

            except Exception as e:
                self.stats["errors"].append(f"Failed to migrate logs: {e}")
                print(f"  ERROR: {e}")

    def _migrate_anomalies(self):
        """Migrate anomalies to tenant-scoped index"""
        new_anomalies_index = f"soc-anomalies-{self.default_org_id}"

        if not self.es.indices.exists(index=self.old_indices["anomalies"]):
            print("  No anomalies index found, skipping...")
            return

        try:
            count_result = self.es.count(index=self.old_indices["anomalies"])
            total = count_result.get("count", 0)
            print(f"  Found {total} anomalies to migrate")
        except Exception as e:
            print(f"  Error counting anomalies: {e}")
            return

        if total == 0:
            return

        if self.dry_run:
            print(f"  [DRY RUN] Would migrate {total} anomalies to {new_anomalies_index}")
        else:
            try:
                if not self.es.indices.exists(index=new_anomalies_index):
                    old_mapping = self.es.indices.get_mapping(index=self.old_indices["anomalies"])
                    mappings = old_mapping[self.old_indices["anomalies"]].get("mappings", {})

                    self.es.indices.create(
                        index=new_anomalies_index,
                        mappings=mappings
                    )

                result = reindex(
                    self.es,
                    source_index=self.old_indices["anomalies"],
                    target_index=new_anomalies_index
                )
                self.stats["anomalies_migrated"] = result[0]
                print(f"  Migrated {result[0]} anomalies")

            except Exception as e:
                self.stats["errors"].append(f"Failed to migrate anomalies: {e}")
                print(f"  ERROR: {e}")

    def _migrate_incidents(self):
        """Migrate incidents to tenant-scoped index"""
        new_incidents_index = f"soc-incidents-{self.default_org_id}"

        if not self.es.indices.exists(index=self.old_indices["incidents"]):
            print("  No incidents index found, skipping...")
            return

        try:
            count_result = self.es.count(index=self.old_indices["incidents"])
            total = count_result.get("count", 0)
            print(f"  Found {total} incidents to migrate")
        except Exception as e:
            print(f"  Error counting incidents: {e}")
            return

        if total == 0:
            return

        if self.dry_run:
            print(f"  [DRY RUN] Would migrate {total} incidents to {new_incidents_index}")
        else:
            try:
                if not self.es.indices.exists(index=new_incidents_index):
                    old_mapping = self.es.indices.get_mapping(index=self.old_indices["incidents"])
                    mappings = old_mapping[self.old_indices["incidents"]].get("mappings", {})

                    self.es.indices.create(
                        index=new_incidents_index,
                        mappings=mappings
                    )

                result = reindex(
                    self.es,
                    source_index=self.old_indices["incidents"],
                    target_index=new_incidents_index
                )
                self.stats["incidents_migrated"] = result[0]
                print(f"  Migrated {result[0]} incidents")

            except Exception as e:
                self.stats["errors"].append(f"Failed to migrate incidents: {e}")
                print(f"  ERROR: {e}")

    def _delete_old_indices(self):
        """Delete old indices after successful migration"""
        indices_to_delete = [
            self.old_indices["logs"],
            self.old_indices["anomalies"],
            self.old_indices["incidents"]
        ]

        for index_name in indices_to_delete:
            try:
                if self.es.indices.exists(index=index_name):
                    self.es.indices.delete(index=index_name)
                    print(f"  Deleted index: {index_name}")
            except Exception as e:
                self.stats["errors"].append(f"Failed to delete {index_name}: {e}")
                print(f"  ERROR deleting {index_name}: {e}")

    def _print_summary(self):
        """Print migration summary"""
        print()
        print("=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"Default Organization ID: {self.default_org_id}")
        print(f"Users Updated: {self.stats['users_updated']}")
        print(f"Logs Migrated: {self.stats['logs_migrated']}")
        print(f"Anomalies Migrated: {self.stats['anomalies_migrated']}")
        print(f"Incidents Migrated: {self.stats['incidents_migrated']}")

        if self.stats["errors"]:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for error in self.stats["errors"]:
                print(f"  - {error}")
        else:
            print("\nNo errors encountered!")

        if self.dry_run:
            print("\n[DRY RUN] No changes were made. Run without --dry-run to execute migration.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate existing data to multi-tenant structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making any modifications"
    )
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="Delete old indices after successful migration"
    )

    args = parser.parse_args()

    migration = MultiTenancyMigration(dry_run=args.dry_run)
    migration.run(delete_old=args.delete_old)


if __name__ == "__main__":
    main()
