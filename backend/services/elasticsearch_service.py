"""
Elasticsearch service for storing and retrieving logs, anomalies, and incidents
Supports multi-tenancy with organization-scoped indices
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.models.schemas import LogEntry, AnomalyResult, Incident, IncidentStatus, TenantContext
from backend.utils import utc_isoformat


class ElasticsearchService:
    """Base Elasticsearch service with index configurations"""

    _indices_config = {
        "logs": {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "client_ip": {"type": "keyword"},
                    "method": {"type": "keyword"},
                    "path": {"type": "keyword"},
                    "status_code": {"type": "integer"},
                    "latency_ms": {"type": "float"},
                    "user_agent": {"type": "text"},
                    "request_size_bytes": {"type": "integer"},
                    "response_size_bytes": {"type": "integer"},
                    "user_id": {"type": "keyword"},
                    "session_id": {"type": "keyword"},
                    "geo_country": {"type": "keyword"},
                    "geo_city": {"type": "keyword"},
                    "is_authenticated": {"type": "boolean"},
                    "error_message": {"type": "text"}
                }
            }
        },
        "anomalies": {
            "mappings": {
                "properties": {
                    "timestamp": {"type": "date"},
                    "anomaly_score": {"type": "float"},
                    "is_anomaly": {"type": "boolean"},
                    "features": {"type": "object"},
                    "source_ips": {"type": "keyword"},
                    "affected_paths": {"type": "keyword"},
                    "window_start": {"type": "date"},
                    "window_end": {"type": "date"}
                }
            }
        },
        "incidents": {
            "mappings": {
                "properties": {
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "status": {"type": "keyword"},
                    "anomaly": {"type": "object"},
                    "classification": {"type": "object"},
                    "recommended_actions": {"type": "nested"},
                    "selected_action": {"type": "object"},
                    "decision_reasoning": {"type": "text"},
                    "agent_logs": {"type": "nested"},
                    "human_feedback": {"type": "text"},
                    "execution_result": {"type": "object"}
                }
            }
        }
    }

    def __init__(self):
        self.es = Elasticsearch(hosts=[settings.ELASTICSEARCH_HOST])
        self._initialized = False
        self._tenant_indices_initialized: set = set()

    def _ensure_indices(self):
        """Create default indices if they don't exist (for backwards compatibility)"""
        if self._initialized:
            return

        index_mapping = {
            settings.ELASTICSEARCH_INDEX_LOGS: self._indices_config["logs"],
            settings.ELASTICSEARCH_INDEX_ANOMALIES: self._indices_config["anomalies"],
            settings.ELASTICSEARCH_INDEX_INCIDENTS: self._indices_config["incidents"],
        }

        for index_name, mapping in index_mapping.items():
            try:
                exists = self.es.indices.exists(index=index_name)
                if not exists:
                    self.es.indices.create(index=index_name, mappings=mapping["mappings"])
            except Exception as e:
                print(f"Error checking/creating index {index_name}: {e}")
                raise

        self._initialized = True

    def ensure_tenant_indices(self, tenant: TenantContext) -> bool:
        """Create all indices for a tenant if they don't exist"""
        if tenant.org_id in self._tenant_indices_initialized:
            return True

        indices_to_create = {
            tenant.logs_index: self._indices_config["logs"],
            tenant.anomalies_index: self._indices_config["anomalies"],
            tenant.incidents_index: self._indices_config["incidents"],
            tenant.metrics_index: self._indices_config["logs"],  # Same mapping as logs for now
        }

        try:
            for index_name, mapping in indices_to_create.items():
                if not self.es.indices.exists(index=index_name):
                    self.es.indices.create(index=index_name, mappings=mapping["mappings"])
                    print(f"[ES] Created tenant index: {index_name}")

            self._tenant_indices_initialized.add(tenant.org_id)
            return True
        except Exception as e:
            print(f"[ES] Error creating tenant indices: {e}")
            return False

    # ============= Legacy methods (for backwards compatibility) =============

    def index_log(self, log: LogEntry) -> str:
        """Index a single log entry (legacy, non-tenant)"""
        result = self.es.index(
            index=settings.ELASTICSEARCH_INDEX_LOGS,
            document=log.model_dump(mode='json')
        )
        return result['_id']

    def bulk_index_logs(self, logs: List[LogEntry]) -> int:
        """Bulk index multiple log entries (legacy, non-tenant)"""
        actions = [
            {
                "_index": settings.ELASTICSEARCH_INDEX_LOGS,
                "_source": log.model_dump(mode='json')
            }
            for log in logs
        ]
        success, _ = bulk(self.es, actions)
        return success

    def get_logs_window(self, start: datetime, end: datetime, size: int = 1000) -> List[Dict]:
        """Get logs within a time window (legacy, non-tenant)"""
        index_pattern = getattr(settings, 'ELASTICSEARCH_INDEX_LOGS_PATTERN', settings.ELASTICSEARCH_INDEX_LOGS)
        return self._get_logs_window_internal(index_pattern, start, end, size)

    def get_all_logs(self, size: int = 1000) -> List[Dict]:
        """Get all logs regardless of time window (legacy, non-tenant)"""
        index_pattern = getattr(settings, 'ELASTICSEARCH_INDEX_LOGS_PATTERN', settings.ELASTICSEARCH_INDEX_LOGS)
        return self._get_all_logs_internal(index_pattern, size)

    def get_aggregated_features(self, start: datetime, end: datetime) -> Dict[str, Any]:
        """Get aggregated features for anomaly detection (legacy, non-tenant)"""
        index_pattern = getattr(settings, 'ELASTICSEARCH_INDEX_LOGS_PATTERN', settings.ELASTICSEARCH_INDEX_LOGS)
        return self._get_aggregated_features_internal(index_pattern, start, end)

    def index_anomaly(self, anomaly: AnomalyResult) -> str:
        """Index an anomaly result (legacy, non-tenant)"""
        result = self.es.index(
            index=settings.ELASTICSEARCH_INDEX_ANOMALIES,
            document=anomaly.model_dump(mode='json')
        )
        return result['_id']

    def index_incident(self, incident: Incident) -> str:
        """Index an incident (legacy, non-tenant)"""
        return self._index_incident_internal(settings.ELASTICSEARCH_INDEX_INCIDENTS, incident)

    def update_incident(self, incident_id: str, updates: Dict[str, Any]) -> bool:
        """Update an incident (legacy, non-tenant)"""
        return self._update_incident_internal(settings.ELASTICSEARCH_INDEX_INCIDENTS, incident_id, updates)

    def get_incident(self, incident_id: str) -> Optional[Dict]:
        """Get a single incident by ID (legacy, non-tenant)"""
        return self._get_incident_internal(settings.ELASTICSEARCH_INDEX_INCIDENTS, incident_id)

    def get_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get incidents with optional filtering (legacy, non-tenant)"""
        return self._get_incidents_internal(settings.ELASTICSEARCH_INDEX_INCIDENTS, status, limit, offset)

    def get_pending_incidents(self) -> List[Dict]:
        """Get all pending approval incidents (legacy, non-tenant)"""
        return self.get_incidents(status=IncidentStatus.PENDING_APPROVAL)

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get metrics for dashboard (legacy, non-tenant)"""
        return self._get_dashboard_metrics_internal(
            settings.ELASTICSEARCH_INDEX_INCIDENTS,
            settings.ELASTICSEARCH_INDEX_ANOMALIES
        )

    def get_blocked_ips(self) -> List[str]:
        """Get list of blocked IPs from executed incidents (legacy, non-tenant)"""
        return self._get_blocked_ips_internal(settings.ELASTICSEARCH_INDEX_INCIDENTS)

    # ============= Tenant-aware methods =============

    def index_log_tenant(self, tenant: TenantContext, log: LogEntry) -> str:
        """Index a single log entry for a tenant"""
        self.ensure_tenant_indices(tenant)
        result = self.es.index(
            index=tenant.logs_index,
            document=log.model_dump(mode='json')
        )
        return result['_id']

    def bulk_index_logs_tenant(self, tenant: TenantContext, logs: List[LogEntry]) -> int:
        """Bulk index multiple log entries for a tenant"""
        self.ensure_tenant_indices(tenant)
        actions = [
            {
                "_index": tenant.logs_index,
                "_source": log.model_dump(mode='json')
            }
            for log in logs
        ]
        success, _ = bulk(self.es, actions)
        return success

    def get_logs_window_tenant(
        self,
        tenant: TenantContext,
        start: datetime,
        end: datetime,
        size: int = 1000
    ) -> List[Dict]:
        """Get logs within a time window for a tenant.
        Falls back to global date-based indices if tenant-specific indices are empty.
        """
        self.ensure_tenant_indices(tenant)
        # Try tenant-specific indices first
        logs = self._get_logs_window_internal(tenant.logs_index_pattern, start, end, size)

        # Fallback to global date-based indices (soc-logs-YYYY.MM.DD) if empty
        if not logs:
            logs = self._get_logs_window_internal("soc-logs-*", start, end, size)

        return logs

    def get_all_logs_tenant(self, tenant: TenantContext, size: int = 1000) -> List[Dict]:
        """Get all logs for a tenant.
        Falls back to global date-based indices if tenant-specific indices are empty.
        """
        self.ensure_tenant_indices(tenant)
        # Try tenant-specific indices first
        logs = self._get_all_logs_internal(tenant.logs_index_pattern, size)

        # Fallback to global date-based indices if empty
        if not logs:
            logs = self._get_all_logs_internal("soc-logs-*", size)

        return logs

    def get_aggregated_features_tenant(
        self,
        tenant: TenantContext,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """Get aggregated features for anomaly detection for a tenant"""
        self.ensure_tenant_indices(tenant)
        return self._get_aggregated_features_internal(tenant.logs_index_pattern, start, end)

    def index_anomaly_tenant(self, tenant: TenantContext, anomaly: AnomalyResult) -> str:
        """Index an anomaly result for a tenant"""
        self.ensure_tenant_indices(tenant)
        result = self.es.index(
            index=tenant.anomalies_index,
            document=anomaly.model_dump(mode='json')
        )
        return result['_id']

    def index_incident_tenant(self, tenant: TenantContext, incident: Incident) -> str:
        """Index an incident for a tenant"""
        self.ensure_tenant_indices(tenant)
        return self._index_incident_internal(tenant.incidents_index, incident)

    def update_incident_tenant(
        self,
        tenant: TenantContext,
        incident_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update an incident for a tenant"""
        return self._update_incident_internal(tenant.incidents_index, incident_id, updates)

    def get_incident_tenant(self, tenant: TenantContext, incident_id: str) -> Optional[Dict]:
        """Get a single incident by ID for a tenant"""
        return self._get_incident_internal(tenant.incidents_index, incident_id)

    def get_incidents_tenant(
        self,
        tenant: TenantContext,
        status: Optional[IncidentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get incidents with optional filtering for a tenant"""
        self.ensure_tenant_indices(tenant)
        return self._get_incidents_internal(tenant.incidents_index, status, limit, offset)

    def get_pending_incidents_tenant(self, tenant: TenantContext) -> List[Dict]:
        """Get all pending approval incidents for a tenant"""
        return self.get_incidents_tenant(tenant, status=IncidentStatus.PENDING_APPROVAL)

    def get_dashboard_metrics_tenant(self, tenant: TenantContext) -> Dict[str, Any]:
        """Get metrics for dashboard for a tenant"""
        self.ensure_tenant_indices(tenant)
        return self._get_dashboard_metrics_internal(
            tenant.incidents_index,
            tenant.anomalies_index
        )

    def get_blocked_ips_tenant(self, tenant: TenantContext) -> List[str]:
        """Get list of blocked IPs from executed incidents for a tenant"""
        self.ensure_tenant_indices(tenant)
        return self._get_blocked_ips_internal(tenant.incidents_index)

    # ============= Internal methods =============

    def _get_logs_window_internal(
        self,
        index_pattern: str,
        start: datetime,
        end: datetime,
        size: int
    ) -> List[Dict]:
        """Internal method to get logs within a time window.
        Handles both @timestamp (Fluent-bit) and timestamp (API ingested) fields.
        """
        # Use bool query to match either timestamp field
        time_query = {
            "bool": {
                "should": [
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                    {"range": {"timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}}
                ],
                "minimum_should_match": 1
            }
        }

        # Sort with unmapped_type to handle missing fields gracefully
        sort_config = [
            {"@timestamp": {"order": "asc", "unmapped_type": "date"}},
            {"timestamp": {"order": "asc", "unmapped_type": "date"}}
        ]

        try:
            result = self.es.search(
                index=index_pattern,
                query=time_query,
                size=size,
                sort=sort_config
            )
            return self._parse_log_hits(result)
        except Exception as e:
            print(f"[ES] Error getting logs window: {e}")
            # Fallback without sort
            try:
                result = self.es.search(
                    index=index_pattern,
                    query=time_query,
                    size=size
                )
                return self._parse_log_hits(result)
            except Exception as e2:
                print(f"[ES] Error getting logs (no sort): {e2}")
                return []

    def _get_all_logs_internal(self, index_pattern: str, size: int) -> List[Dict]:
        """Internal method to get all logs.
        Handles both @timestamp (Fluent-bit) and timestamp (API ingested) fields.
        """
        # Sort with unmapped_type to handle missing fields gracefully
        sort_config = [
            {"@timestamp": {"order": "desc", "unmapped_type": "date"}},
            {"timestamp": {"order": "desc", "unmapped_type": "date"}}
        ]

        try:
            result = self.es.search(
                index=index_pattern,
                query={"match_all": {}},
                size=size,
                sort=sort_config
            )
            return self._parse_log_hits(result)
        except Exception as e:
            print(f"[ES] Error getting all logs with sort: {e}")
            # Fallback without sort
            try:
                result = self.es.search(
                    index=index_pattern,
                    query={"match_all": {}},
                    size=size
                )
                return self._parse_log_hits(result)
            except Exception as e2:
                print(f"[ES] Error getting all logs: {e2}")
                return []

    def _parse_log_hits(self, result: Dict) -> List[Dict]:
        """Parse log hits from ES response"""
        logs = []
        for hit in result.get('hits', {}).get('hits', []):
            source = hit['_source']
            if 'log' in source and isinstance(source['log'], str):
                try:
                    parsed_log = json.loads(source['log'])
                    if '@timestamp' not in parsed_log and '@timestamp' in source:
                        parsed_log['@timestamp'] = source['@timestamp']
                    logs.append(parsed_log)
                except json.JSONDecodeError:
                    logs.append(source)
            else:
                logs.append(source)
        return logs

    def _get_aggregated_features_internal(
        self,
        index_pattern: str,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """Internal method to get aggregated features.
        Handles both @timestamp and timestamp fields.
        """
        # Build query that works with either timestamp field
        time_query = {
            "bool": {
                "should": [
                    {"range": {"@timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}},
                    {"range": {"timestamp": {"gte": start.isoformat(), "lt": end.isoformat()}}}
                ],
                "minimum_should_match": 1
            }
        }

        try:
            result = self.es.search(
                index=index_pattern,
                size=0,
                query=time_query,
                aggs={
                    "total_requests": {"value_count": {"field": "client_ip"}},
                    "unique_ips": {"cardinality": {"field": "client_ip"}},
                    "unique_paths": {"cardinality": {"field": "path"}},
                    "avg_latency": {"avg": {"field": "latency_ms"}},
                    "status_codes": {
                        "terms": {"field": "status_code", "size": 20}
                    },
                    "top_ips": {
                        "terms": {"field": "client_ip", "size": 50}
                    },
                    "auth_failures": {
                        "filter": {
                            "bool": {
                                "must": [
                                    {"term": {"is_authenticated": False}},
                                    {"range": {"status_code": {"gte": 401, "lte": 403}}}
                                ]
                            }
                        }
                    },
                    "errors_4xx": {
                        "filter": {"range": {"status_code": {"gte": 400, "lt": 500}}}
                    },
                    "errors_5xx": {
                        "filter": {"range": {"status_code": {"gte": 500}}}
                    },
                    "geo_distribution": {
                        "terms": {"field": "geo_country", "size": 50}
                    },
                    "requests_per_minute": {
                        "date_histogram": {
                            "field": "timestamp",
                            "fixed_interval": "1m"
                        }
                    }
                }
            )
            return result.get('aggregations', {})
        except Exception as e:
            print(f"Error getting aggregated features: {e}")
            return {}

    def _index_incident_internal(self, index_name: str, incident: Incident) -> str:
        """Internal method to index an incident"""
        doc = incident.model_dump(mode='json')
        if incident.id:
            self.es.index(
                index=index_name,
                id=incident.id,
                document=doc
            )
            return incident.id
        else:
            result = self.es.index(
                index=index_name,
                document=doc
            )
            return result['_id']

    def _update_incident_internal(
        self,
        index_name: str,
        incident_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Internal method to update an incident"""
        updates['updated_at'] = utc_isoformat()
        try:
            self.es.update(
                index=index_name,
                id=incident_id,
                doc=updates
            )
            return True
        except Exception as e:
            print(f"Error updating incident: {e}")
            return False

    def _get_incident_internal(self, index_name: str, incident_id: str) -> Optional[Dict]:
        """Internal method to get a single incident"""
        try:
            result = self.es.get(
                index=index_name,
                id=incident_id
            )
            incident = result['_source']
            incident['id'] = result['_id']
            return incident
        except Exception:
            return None

    def _get_incidents_internal(
        self,
        index_name: str,
        status: Optional[IncidentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Internal method to get incidents"""
        try:
            query = {"match_all": {}}
            if status:
                query = {"term": {"status": status.value}}

            result = self.es.search(
                index=index_name,
                query=query,
                size=limit,
                from_=offset,
                sort=[{"created_at": "desc"}]
            )
            incidents = []
            for hit in result['hits']['hits']:
                incident = hit['_source']
                incident['id'] = hit['_id']
                incidents.append(incident)
            return incidents
        except Exception as e:
            print(f"[ES] Error fetching incidents: {e}")
            return []

    def _get_dashboard_metrics_internal(
        self,
        incidents_index: str,
        anomalies_index: str
    ) -> Dict[str, Any]:
        """Internal method to get dashboard metrics"""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        # Get incident counts
        try:
            incident_result = self.es.search(
                index=incidents_index,
                size=0,
                aggs={
                    "status_counts": {
                        "terms": {"field": "status"}
                    },
                    "severity_counts": {
                        "terms": {"field": "classification.severity"}
                    }
                }
            )
        except Exception:
            incident_result = {"aggregations": {}}

        # Get anomaly time series
        two_hours_ago = now - timedelta(hours=2)
        try:
            anomaly_result = self.es.search(
                index=anomalies_index,
                size=0,
                query={
                    "range": {
                        "timestamp": {
                            "gte": two_hours_ago.isoformat(),
                            "lt": now.isoformat()
                        }
                    }
                },
                aggs={
                    "anomalies_over_time": {
                        "date_histogram": {
                            "field": "timestamp",
                            "fixed_interval": "10m"
                        },
                        "aggs": {
                            "anomaly_count": {
                                "filter": {"term": {"is_anomaly": True}}
                            }
                        }
                    }
                }
            )
        except Exception:
            anomaly_result = {"aggregations": {}}

        # Get top risky IPs
        try:
            risky_ip_result = self.es.search(
                index=incidents_index,
                size=0,
                query={
                    "range": {
                        "created_at": {
                            "gte": day_ago.isoformat()
                        }
                    }
                },
                aggs={
                    "risky_ips": {
                        "terms": {"field": "anomaly.source_ips", "size": 10}
                    }
                }
            )
        except Exception:
            risky_ip_result = {"aggregations": {}}

        return {
            "incident_stats": incident_result.get('aggregations', {}),
            "anomaly_time_series": anomaly_result.get('aggregations', {}),
            "risky_ips": risky_ip_result.get('aggregations', {})
        }

    def _get_blocked_ips_internal(self, index_name: str) -> List[str]:
        """Internal method to get blocked IPs"""
        try:
            result = self.es.search(
                index=index_name,
                size=100,
                query={
                    "bool": {
                        "must": [
                            {"term": {"status": "EXECUTED"}},
                            {"term": {"selected_action.action_type": "BLOCK_IP"}}
                        ]
                    }
                }
            )
            blocked_ips = []
            for hit in result['hits']['hits']:
                action = hit['_source'].get('selected_action', {})
                if action.get('target'):
                    blocked_ips.append(action['target'])
            return blocked_ips
        except Exception:
            return []


class TenantAwareElasticsearchService(ElasticsearchService):
    """
    Tenant-aware Elasticsearch service that enforces multi-tenancy.
    All operations require a TenantContext.
    """

    def index_log(self, tenant: TenantContext, log: LogEntry) -> str:
        """Index a single log entry"""
        return self.index_log_tenant(tenant, log)

    def bulk_index_logs(self, tenant: TenantContext, logs: List[LogEntry]) -> int:
        """Bulk index multiple log entries"""
        return self.bulk_index_logs_tenant(tenant, logs)

    def get_logs_window(
        self,
        tenant: TenantContext,
        start: datetime,
        end: datetime,
        size: int = 1000
    ) -> List[Dict]:
        """Get logs within a time window"""
        return self.get_logs_window_tenant(tenant, start, end, size)

    def get_all_logs(self, tenant: TenantContext, size: int = 1000) -> List[Dict]:
        """Get all logs"""
        return self.get_all_logs_tenant(tenant, size)

    def get_aggregated_features(
        self,
        tenant: TenantContext,
        start: datetime,
        end: datetime
    ) -> Dict[str, Any]:
        """Get aggregated features for anomaly detection"""
        return self.get_aggregated_features_tenant(tenant, start, end)

    def index_anomaly(self, tenant: TenantContext, anomaly: AnomalyResult) -> str:
        """Index an anomaly result"""
        return self.index_anomaly_tenant(tenant, anomaly)

    def index_incident(self, tenant: TenantContext, incident: Incident) -> str:
        """Index an incident"""
        return self.index_incident_tenant(tenant, incident)

    def update_incident(
        self,
        tenant: TenantContext,
        incident_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update an incident"""
        return self.update_incident_tenant(tenant, incident_id, updates)

    def get_incident(self, tenant: TenantContext, incident_id: str) -> Optional[Dict]:
        """Get a single incident by ID"""
        return self.get_incident_tenant(tenant, incident_id)

    def get_incidents(
        self,
        tenant: TenantContext,
        status: Optional[IncidentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """Get incidents with optional filtering"""
        return self.get_incidents_tenant(tenant, status, limit, offset)

    def get_pending_incidents(self, tenant: TenantContext) -> List[Dict]:
        """Get all pending approval incidents"""
        return self.get_pending_incidents_tenant(tenant)

    def get_dashboard_metrics(self, tenant: TenantContext) -> Dict[str, Any]:
        """Get metrics for dashboard"""
        return self.get_dashboard_metrics_tenant(tenant)

    def get_blocked_ips(self, tenant: TenantContext) -> List[str]:
        """Get list of blocked IPs from executed incidents"""
        return self.get_blocked_ips_tenant(tenant)


def get_es_service() -> ElasticsearchService:
    """Get or create the ES service singleton. Call _ensure_indices() on first use."""
    if not hasattr(get_es_service, "_instance"):
        get_es_service._instance = ElasticsearchService()
    return get_es_service._instance


def get_tenant_es_service() -> TenantAwareElasticsearchService:
    """Get or create the tenant-aware ES service singleton."""
    if not hasattr(get_tenant_es_service, "_instance"):
        get_tenant_es_service._instance = TenantAwareElasticsearchService()
    return get_tenant_es_service._instance


# For backwards compatibility - but prefer using get_es_service()
es_service: ElasticsearchService = None  # type: ignore


def init_es_service():
    """Initialize ES service and create indices. Call from FastAPI startup."""
    global es_service
    es_service = get_es_service()
    es_service._ensure_indices()
