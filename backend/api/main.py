"""
FastAPI Backend - SOC Analyst API with Multi-Tenancy Support
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState
from typing import List, Optional, Set, Dict
from datetime import datetime, timedelta
import asyncio
import json
import logging

# Configure logging for WebSocket errors
logger = logging.getLogger("soc-api")
logger.setLevel(logging.INFO)

import sys
sys.path.insert(0, '/home/rishikesh/Projects/Autonomous-SOC-Analyst')

from config.settings import settings
from backend.models.schemas import (
    LogEntry, AnomalyResult, Incident, IncidentApproval,
    IncidentStatus, DashboardMetrics, EvaluationMetrics,
    SeverityLevel, ActionType, RecommendedAction, TenantContext
)
from backend.services.elasticsearch_service import (
    get_es_service, get_tenant_es_service, init_es_service
)
from backend.utils import utc_isoformat
from ml.anomaly_detector import anomaly_detector
from agents.workflow import soc_workflow, process_anomaly, approve_incident, get_pending_incidents
from agents.response_agent import response_agent
from backend.auth import auth_router, org_router, get_current_user, get_tenant_context, require_org_membership
from backend.auth.models import User
from backend.auth.dependencies import get_current_user_ws, get_tenant_context_optional
from backend.auth.security import decode_token


app = FastAPI(
    title="Autonomous SOC Analyst API",
    description="AI-powered Security Operations Center with LangGraph Agents and Multi-Tenancy",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(org_router)

# Routes that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/api/status",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/token",
    "/docs",
    "/redoc",
    "/openapi.json",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Authentication middleware that protects all routes except public ones.
    Also extracts tenant info from JWT and adds to request state.
    """
    path = request.url.path

    # Allow public paths
    if path in PUBLIC_PATHS or path.startswith("/api/auth/"):
        return await call_next(request)

    # Allow WebSocket upgrade requests (auth handled in WebSocket endpoint)
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    # Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validate Bearer token
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authentication scheme"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Add user and tenant info to request state
        request.state.user_id = payload.get("sub")
        request.state.user_email = payload.get("email")
        request.state.org_id = payload.get("org_id")
        request.state.org_role = payload.get("org_role")

    except ValueError:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authorization header format"},
            headers={"WWW-Authenticate": "Bearer"}
        )

    return await call_next(request)


# Background task state
anomaly_detection_running = False

# ES service references (set on startup)
es_service = None
tenant_es_service = None


# WebSocket connection manager with tenant support
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}  # org_id -> connections
        self.broadcast_tasks: Dict[str, asyncio.Task] = {}  # org_id -> task
        self._lock = asyncio.Lock()
        self._connection_id = 0

    async def connect(self, websocket: WebSocket, org_id: Optional[str] = None):
        async with self._lock:
            await websocket.accept()
            self._connection_id += 1
            conn_id = self._connection_id

            # Use org_id or "global" for non-tenant connections
            tenant_key = org_id or "global"
            if tenant_key not in self.active_connections:
                self.active_connections[tenant_key] = []

            self.active_connections[tenant_key].append(websocket)
            logger.info(f"[WebSocket] Client #{conn_id} connected to tenant {tenant_key}. Total connections: {len(self.active_connections[tenant_key])}")

            # Start broadcast task if not running for this tenant
            if tenant_key not in self.broadcast_tasks or self.broadcast_tasks[tenant_key].done():
                self.broadcast_tasks[tenant_key] = asyncio.create_task(
                    self.periodic_broadcast(tenant_key, org_id)
                )

    def disconnect(self, websocket: WebSocket, org_id: Optional[str] = None):
        tenant_key = org_id or "global"
        if tenant_key in self.active_connections and websocket in self.active_connections[tenant_key]:
            self.active_connections[tenant_key].remove(websocket)
            logger.info(f"[WebSocket] Client disconnected from tenant {tenant_key}. Remaining: {len(self.active_connections[tenant_key])}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific websocket with proper error handling"""
        try:
            await websocket.send_json(message)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            logger.debug(f"[WebSocket] Client disconnected during send: {type(e).__name__}")
            return False
        except RuntimeError as e:
            err_str = str(e).lower()
            if "disconnect" in err_str or "closed" in err_str or "websocket" in err_str:
                return False
            logger.warning(f"[WebSocket] Runtime error during send: {e}")
            return False
        except Exception as e:
            logger.warning(f"[WebSocket] Unexpected error during send: {type(e).__name__}: {e}")
            return False

    async def broadcast(self, message: dict, org_id: Optional[str] = None):
        """Broadcast message to all connected clients for a tenant"""
        tenant_key = org_id or "global"
        if tenant_key not in self.active_connections or not self.active_connections[tenant_key]:
            return

        connections = self.active_connections[tenant_key].copy()
        disconnected = []

        for connection in connections:
            try:
                await connection.send_json(message)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                disconnected.append(connection)
            except RuntimeError as e:
                err_str = str(e).lower()
                if "disconnect" in err_str or "closed" in err_str or "websocket" in err_str:
                    disconnected.append(connection)
                else:
                    logger.warning(f"[WebSocket] Runtime error during broadcast: {e}")
                    disconnected.append(connection)
            except Exception as e:
                logger.warning(f"[WebSocket] Error broadcasting to client: {type(e).__name__}: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn, org_id)

    async def get_dashboard_data(self, org_id: Optional[str] = None) -> dict:
        """Fetch all dashboard data for a tenant"""
        default_metrics = {
            "total_incidents": 0,
            "pending_approval": 0,
            "blocked_ips": 0,
            "severity_distribution": {},
            "status_distribution": {},
            "time_series_anomalies": [],
            "top_risky_ips": [],
            "recent_incidents": []
        }
        default_status = {
            "elasticsearch": "disconnected",
            "anomaly_detector": "not_trained",
            "groq_api": "not_configured",
            "detection_running": False,
            "pending_incidents": 0
        }

        try:
            if es_service is None:
                logger.warning("[WebSocket] ES service not initialized")
                return {
                    "metrics": default_metrics,
                    "logs": {"logs": []},
                    "status": default_status
                }

            # Use tenant-aware service - require org_id for data isolation
            if org_id and tenant_es_service:
                from backend.auth.organization_service import organization_service
                org = organization_service.get_organization_by_id(org_id)
                if org:
                    tenant = TenantContext(
                        org_id=org_id,
                        org_slug=org.slug,
                        user_id="system",
                        user_role="SYSTEM"
                    )
                    es_metrics = tenant_es_service.get_dashboard_metrics(tenant)
                    blocked_count = len(response_agent.get_blocked_ips_for_org(org_id)) if hasattr(response_agent, 'get_blocked_ips_for_org') else len(response_agent.blocked_ips)
                    recent = tenant_es_service.get_incidents(tenant, limit=10)
                    incidents_for_logs = tenant_es_service.get_incidents(tenant, limit=20)
                else:
                    # Organization not found - return empty data
                    logger.warning(f"[WebSocket] Organization not found: {org_id}")
                    return {
                        "metrics": default_metrics,
                        "logs": {"logs": []},
                        "status": default_status
                    }
            else:
                # No org_id provided - return empty data for tenant isolation
                logger.warning("[WebSocket] No org_id provided, returning empty data")
                return {
                    "metrics": default_metrics,
                    "logs": {"logs": []},
                    "status": default_status
                }

            incident_stats = es_metrics.get('incident_stats', {})
            status_buckets = incident_stats.get('status_counts', {}).get('buckets', [])
            severity_buckets = incident_stats.get('severity_counts', {}).get('buckets', [])

            status_counts = {b['key']: b['doc_count'] for b in status_buckets}
            severity_counts = {b['key']: b['doc_count'] for b in severity_buckets}

            anomaly_ts = es_metrics.get('anomaly_time_series', {})
            time_buckets = anomaly_ts.get('anomalies_over_time', {}).get('buckets', [])
            time_series = [
                {
                    'timestamp': b['key_as_string'],
                    'total': b['doc_count'],
                    'anomalies': b.get('anomaly_count', {}).get('doc_count', 0)
                }
                for b in time_buckets
            ]

            risky_ips_agg = es_metrics.get('risky_ips', {})
            risky_buckets = risky_ips_agg.get('risky_ips', {}).get('buckets', [])
            top_risky_ips = [
                {'ip': b['key'], 'count': b['doc_count']}
                for b in risky_buckets
            ]

            metrics = {
                "total_incidents": sum(status_counts.values()),
                "pending_approval": status_counts.get('PENDING_APPROVAL', 0) + len(soc_workflow.pending_incidents),
                "blocked_ips": blocked_count,
                "severity_distribution": severity_counts,
                "status_distribution": status_counts,
                "time_series_anomalies": time_series,
                "top_risky_ips": top_risky_ips,
                "recent_incidents": recent
            }

            # Get logs
            all_logs = []
            for inc in incidents_for_logs:
                logs = inc.get('agent_logs', [])
                for log in logs:
                    log['incident_id'] = inc.get('id')
                all_logs.extend(logs)
            all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

            # Get status
            es_healthy = False
            try:
                if es_service and es_service.es:
                    es_healthy = es_service.es.ping()
            except Exception:
                es_healthy = False

            status = {
                "elasticsearch": "connected" if es_healthy else "disconnected",
                "anomaly_detector": "ready" if anomaly_detector and anomaly_detector.is_fitted else "not_trained",
                "groq_api": "configured" if settings.GROQ_API_KEY else "not_configured",
                "detection_running": anomaly_detection_running,
                "pending_incidents": len(soc_workflow.pending_incidents) if soc_workflow else 0
            }

            return {
                "metrics": metrics,
                "logs": {"logs": all_logs[:20]},
                "status": status
            }
        except Exception as e:
            logger.error(f"[WebSocket] Error fetching dashboard data: {type(e).__name__}: {e}")
            return {
                "metrics": default_metrics,
                "logs": {"logs": []},
                "status": default_status
            }

    async def periodic_broadcast(self, tenant_key: str, org_id: Optional[str] = None):
        """Periodically broadcast updates to all connected clients for a tenant"""
        empty_cycles = 0
        max_empty_cycles = 6

        while True:
            try:
                if tenant_key not in self.active_connections or not self.active_connections[tenant_key]:
                    empty_cycles += 1
                    if empty_cycles >= max_empty_cycles:
                        logger.info(f"[WebSocket] No connections for tenant {tenant_key} for 30s, stopping broadcast")
                        break
                    await asyncio.sleep(5)
                    continue

                empty_cycles = 0
                data = await self.get_dashboard_data(org_id)
                if data and self.active_connections.get(tenant_key):
                    await self.broadcast({
                        "type": "full_update",
                        "data": data,
                        "timestamp": utc_isoformat()
                    }, org_id)

            except asyncio.CancelledError:
                logger.info(f"[WebSocket] Periodic broadcast cancelled for tenant {tenant_key}")
                break
            except (BrokenPipeError, ConnectionResetError) as e:
                logger.debug(f"[WebSocket] Connection error in periodic broadcast: {type(e).__name__}")
            except Exception as e:
                logger.warning(f"[WebSocket] Broadcast error: {type(e).__name__}: {e}")

            await asyncio.sleep(5)


ws_manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global es_service, tenant_es_service
    init_es_service()
    from backend.services.elasticsearch_service import es_service as _es_service
    es_service = _es_service
    tenant_es_service = get_tenant_es_service()


# ============= Health & Status =============

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": utc_isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/status")
async def system_status():
    """Get system status"""
    es_healthy = False
    try:
        if es_service and es_service.es:
            es_healthy = es_service.es.ping()
    except Exception:
        es_healthy = False

    return {
        "elasticsearch": "connected" if es_healthy else "disconnected",
        "anomaly_detector": "ready" if anomaly_detector and anomaly_detector.is_fitted else "not_trained",
        "groq_api": "configured" if settings.GROQ_API_KEY else "not_configured",
        "detection_running": anomaly_detection_running,
        "pending_incidents": len(soc_workflow.pending_incidents) if soc_workflow else 0
    }


# ============= WebSocket =============

@app.websocket("/api/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time dashboard updates (requires auth token in query param)"""
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    org_id = payload.get("org_id")

    try:
        await ws_manager.connect(websocket, org_id)
    except Exception as e:
        logger.error(f"[WebSocket] Failed to accept connection: {e}")
        return

    try:
        initial_data = await ws_manager.get_dashboard_data(org_id)
        send_success = await ws_manager.send_personal_message({
            "type": "full_update",
            "data": initial_data,
            "timestamp": utc_isoformat()
        }, websocket)

        if not send_success:
            return

        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get('type')

                if msg_type == 'refresh':
                    channel = data.get('channel', 'all')
                    dashboard_data = await ws_manager.get_dashboard_data(org_id)

                    if channel == 'all':
                        await ws_manager.send_personal_message({
                            "type": "full_update",
                            "data": dashboard_data,
                            "timestamp": utc_isoformat()
                        }, websocket)
                    elif channel == 'metrics':
                        await ws_manager.send_personal_message({
                            "type": "metrics",
                            "data": dashboard_data.get('metrics'),
                            "timestamp": utc_isoformat()
                        }, websocket)
                    elif channel == 'logs':
                        await ws_manager.send_personal_message({
                            "type": "logs",
                            "data": dashboard_data.get('logs'),
                            "timestamp": utc_isoformat()
                        }, websocket)
                    elif channel == 'status':
                        await ws_manager.send_personal_message({
                            "type": "status",
                            "data": dashboard_data.get('status'),
                            "timestamp": utc_isoformat()
                        }, websocket)

                elif msg_type == 'subscribe':
                    await ws_manager.send_personal_message({
                        "type": "subscribed",
                        "channels": data.get('channels', []),
                        "timestamp": utc_isoformat()
                    }, websocket)

            except WebSocketDisconnect:
                break
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                break
            except RuntimeError as e:
                if "disconnect" in str(e).lower() or "closed" in str(e).lower():
                    break
                logger.warning(f"[WebSocket] Runtime error: {e}")
            except Exception as e:
                logger.warning(f"[WebSocket] Message error: {type(e).__name__}: {e}")

    except WebSocketDisconnect:
        pass
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
        pass
    except Exception as e:
        logger.error(f"[WebSocket] Unexpected error: {type(e).__name__}: {e}")
    finally:
        ws_manager.disconnect(websocket, org_id)


async def notify_incident_update(incident_id: str, org_id: Optional[str] = None):
    """Notify all connected clients about an incident update"""
    await ws_manager.broadcast({
        "type": "incident_update",
        "incident_id": incident_id,
        "timestamp": utc_isoformat()
    }, org_id)


# ============= Log Ingestion (Tenant-aware) =============

@app.post("/api/logs")
async def ingest_log(
    log: LogEntry,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Ingest a single log entry for the tenant"""
    try:
        log_id = tenant_es_service.index_log(tenant, log)
        return {"status": "success", "id": log_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/logs/bulk")
async def ingest_logs_bulk(
    logs: List[LogEntry],
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Bulk ingest log entries for the tenant"""
    try:
        count = tenant_es_service.bulk_index_logs(tenant, logs)
        return {"status": "success", "indexed": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
async def get_logs(
    tenant: TenantContext = Depends(get_tenant_context),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000)
):
    """Get logs within a time range for the tenant"""
    if not start:
        start = datetime.utcnow() - timedelta(hours=1)
    if not end:
        end = datetime.utcnow()

    try:
        logs = tenant_es_service.get_logs_window(tenant, start, end, limit)
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Anomaly Detection (Tenant-aware) =============

@app.post("/api/anomaly/detect")
async def detect_anomalies(
    tenant: TenantContext = Depends(get_tenant_context),
    window_minutes: int = Query(default=5, ge=1, le=60)
):
    """Run anomaly detection on recent logs for the tenant"""
    end = datetime.utcnow()
    start = end - timedelta(minutes=window_minutes)

    try:
        logs = tenant_es_service.get_logs_window(tenant, start, end)

        if not logs:
            return {"anomaly": None, "message": "No logs in window"}

        result = anomaly_detector.predict(logs)
        result_id = tenant_es_service.index_anomaly(tenant, result)
        result.id = result_id

        return {
            "anomaly": result.model_dump(mode='json'),
            "log_count": len(logs)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/anomaly/detect-per-ip")
async def detect_anomalies_per_ip(
    tenant: TenantContext = Depends(get_tenant_context),
    window_minutes: int = Query(default=5, ge=1, le=60)
):
    """Run anomaly detection per IP for the tenant"""
    end = datetime.utcnow()
    start = end - timedelta(minutes=window_minutes)

    try:
        logs = tenant_es_service.get_logs_window(tenant, start, end)

        if not logs:
            return {"anomalies": {}, "message": "No logs in window"}

        results = anomaly_detector.predict_per_ip(logs)
        anomalous = {
            ip: result.model_dump(mode='json')
            for ip, result in results.items()
            if result.is_anomaly
        }

        return {
            "anomalies": anomalous,
            "total_ips": len(results),
            "anomalous_count": len(anomalous)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/anomaly/train")
async def train_anomaly_detector(
    tenant: TenantContext = Depends(get_tenant_context),
    hours: int = Query(default=24, ge=1, le=168)
):
    """Train the anomaly detector on historical data for the tenant"""
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)

    try:
        logs = tenant_es_service.get_logs_window(tenant, start, end, size=10000)

        logger.info(f"[Training] Found {len(logs)} logs in the last {hours} hours")

        if len(logs) < 100:
            logger.info("[Training] Not enough logs in time window, fetching all available logs...")
            all_logs = tenant_es_service.get_all_logs(tenant, size=10000)
            logger.info(f"[Training] Found {len(all_logs)} total logs in index")

            if len(all_logs) >= 100:
                logs = all_logs
            else:
                return {"status": "insufficient_data", "log_count": len(all_logs)}

        window_size = 50
        windows = [
            logs[i:i+window_size]
            for i in range(0, len(logs), window_size)
            if len(logs[i:i+window_size]) >= 10
        ]

        if not windows:
            return {"status": "no_valid_windows", "log_count": len(logs)}

        logger.info(f"[Training] Training on {len(windows)} windows")
        anomaly_detector.fit(windows)

        if not anomaly_detector.is_fitted:
            return {"status": "training_failed", "log_count": len(logs)}

        return {
            "status": "success",
            "windows_trained": len(windows),
            "total_logs": len(logs)
        }

    except Exception as e:
        logger.error(f"[Training] Error during training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Agent Workflow (Tenant-aware) =============

@app.post("/api/incidents/process")
async def process_incident(
    tenant: TenantContext = Depends(get_tenant_context),
    window_minutes: int = Query(default=5, ge=1, le=60)
):
    """Detect anomalies and process through agent workflow for the tenant"""
    end = datetime.utcnow()
    start = end - timedelta(minutes=window_minutes)

    try:
        logs = tenant_es_service.get_logs_window(tenant, start, end)

        if not logs:
            return {"incident": None, "message": "No logs in window"}

        anomaly_result = anomaly_detector.predict(logs)

        if not anomaly_result.is_anomaly:
            return {
                "incident": None,
                "message": "No anomaly detected",
                "anomaly_score": anomaly_result.anomaly_score
            }

        # Process through agent workflow with tenant context
        incident = process_anomaly(anomaly_result, logs, tenant_context=tenant.to_dict())
        incident_id = tenant_es_service.index_incident(tenant, incident)
        incident.id = incident_id

        return {"incident": incident.model_dump(mode='json')}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/incidents")
async def get_incidents(
    tenant: TenantContext = Depends(get_tenant_context),
    status: Optional[IncidentStatus] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """Get incidents with optional filtering for the tenant"""
    try:
        incidents = tenant_es_service.get_incidents(tenant, status=status, limit=limit, offset=offset)
        return {"incidents": incidents, "count": len(incidents)}
    except Exception as e:
        logger.error(f"[Incidents] Error fetching incidents: {type(e).__name__}: {e}")
        return {"incidents": [], "count": 0}


@app.get("/api/incidents/pending")
async def get_pending_incidents_api(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get incidents pending human approval for the tenant"""
    try:
        workflow_pending = get_pending_incidents()
        es_pending = tenant_es_service.get_pending_incidents(tenant)

        all_pending = [i.model_dump(mode='json') for i in workflow_pending]

        workflow_ids = {i.get('id') for i in all_pending if i.get('id')}
        for inc in es_pending:
            if inc.get('id') not in workflow_ids:
                all_pending.append(inc)

        return {"incidents": all_pending, "count": len(all_pending)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get a specific incident for the tenant"""
    try:
        incident = tenant_es_service.get_incident(tenant, incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident": incident}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/incidents/{incident_id}/approve")
async def approve_incident_api(
    incident_id: str,
    approval: IncidentApproval,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Approve or deny an incident for the tenant"""
    approval.incident_id = incident_id

    try:
        try:
            incident = approve_incident(approval)
            tenant_es_service.index_incident(tenant, incident)
            return {"incident": incident.model_dump(mode='json')}
        except ValueError:
            updates = {
                "status": IncidentStatus.APPROVED.value if approval.approved else IncidentStatus.DENIED.value,
                "human_feedback": approval.feedback
            }

            if approval.approved:
                es_incident = tenant_es_service.get_incident(tenant, incident_id)
                if es_incident and es_incident.get('selected_action'):
                    action_data = es_incident['selected_action']
                    action = RecommendedAction(**action_data)

                    from agents.agent_state import AgentState
                    state = {
                        'selected_action': action,
                        'incident_status': IncidentStatus.APPROVED,
                        'requires_human_approval': False,
                        'tenant_context': tenant.to_dict()
                    }
                    state = response_agent.execute(state)

                    updates['execution_result'] = state.get('execution_result')
                    updates['status'] = IncidentStatus.EXECUTED.value

            tenant_es_service.update_incident(tenant, incident_id, updates)
            return {"status": "success", "updates": updates}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Defensive Actions (Tenant-aware) =============

@app.get("/api/actions/blocked-ips")
async def get_blocked_ips(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get list of blocked IPs for the tenant"""
    blocked = response_agent.get_blocked_ips_for_org(tenant.org_id) if hasattr(response_agent, 'get_blocked_ips_for_org') else response_agent.get_blocked_ips()
    return {
        "blocked_ips": blocked,
        "count": len(blocked)
    }


@app.get("/api/actions/rate-limited")
async def get_rate_limited_ips(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get list of rate-limited IPs for the tenant"""
    rate_limited = response_agent.get_rate_limited_ips_for_org(tenant.org_id) if hasattr(response_agent, 'get_rate_limited_ips_for_org') else response_agent.get_rate_limited_ips()
    return {
        "rate_limited": rate_limited,
        "count": len(rate_limited)
    }


@app.delete("/api/actions/blocked-ips/{ip}")
async def unblock_ip(
    ip: str,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Remove IP from blocked list for the tenant"""
    if hasattr(response_agent, 'unblock_ip_for_org'):
        success = response_agent.unblock_ip_for_org(tenant.org_id, ip)
    else:
        success = response_agent.unblock_ip(ip)
    if not success:
        raise HTTPException(status_code=404, detail="IP not in blocked list")
    return {"status": "success", "message": f"IP {ip} unblocked"}


@app.delete("/api/actions/rate-limited/{ip}")
async def remove_rate_limit(
    ip: str,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Remove rate limit from IP for the tenant"""
    if hasattr(response_agent, 'remove_rate_limit_for_org'):
        success = response_agent.remove_rate_limit_for_org(tenant.org_id, ip)
    else:
        success = response_agent.remove_rate_limit(ip)
    if not success:
        raise HTTPException(status_code=404, detail="IP not in rate-limited list")
    return {"status": "success", "message": f"Rate limit removed from {ip}"}


@app.get("/api/actions/alerts")
async def get_recent_alerts(
    tenant: TenantContext = Depends(get_tenant_context),
    limit: int = Query(default=20, le=100)
):
    """Get recent alerts for the tenant"""
    if hasattr(response_agent, 'get_recent_alerts_for_org'):
        alerts = response_agent.get_recent_alerts_for_org(tenant.org_id, limit)
    else:
        alerts = response_agent.get_recent_alerts(limit)
    return {"alerts": alerts}


@app.get("/api/actions/escalations")
async def get_escalations(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get active escalations for the tenant"""
    if hasattr(response_agent, 'get_active_escalations_for_org'):
        escalations = response_agent.get_active_escalations_for_org(tenant.org_id)
    else:
        escalations = response_agent.get_active_escalations()
    return {"escalations": escalations}


# ============= Dashboard Metrics (Tenant-aware) =============

@app.get("/api/dashboard/metrics")
async def get_dashboard_metrics(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get dashboard metrics for the tenant"""
    try:
        es_metrics = tenant_es_service.get_dashboard_metrics(tenant)

        if hasattr(response_agent, 'get_blocked_ips_for_org'):
            blocked_count = len(response_agent.get_blocked_ips_for_org(tenant.org_id))
        else:
            blocked_count = len(response_agent.blocked_ips)

        incident_stats = es_metrics.get('incident_stats', {})
        status_buckets = incident_stats.get('status_counts', {}).get('buckets', [])
        severity_buckets = incident_stats.get('severity_counts', {}).get('buckets', [])

        status_counts = {b['key']: b['doc_count'] for b in status_buckets}
        severity_counts = {b['key']: b['doc_count'] for b in severity_buckets}

        anomaly_ts = es_metrics.get('anomaly_time_series', {})
        time_buckets = anomaly_ts.get('anomalies_over_time', {}).get('buckets', [])

        time_series = [
            {
                'timestamp': b['key_as_string'],
                'total': b['doc_count'],
                'anomalies': b.get('anomaly_count', {}).get('doc_count', 0)
            }
            for b in time_buckets
        ]

        risky_ips_agg = es_metrics.get('risky_ips', {})
        risky_buckets = risky_ips_agg.get('risky_ips', {}).get('buckets', [])
        top_risky_ips = [
            {'ip': b['key'], 'count': b['doc_count']}
            for b in risky_buckets
        ]

        recent = tenant_es_service.get_incidents(tenant, limit=10)

        return {
            "total_incidents": sum(status_counts.values()),
            "pending_approval": status_counts.get('PENDING_APPROVAL', 0) + len(soc_workflow.pending_incidents),
            "blocked_ips": blocked_count,
            "severity_distribution": severity_counts,
            "status_distribution": status_counts,
            "time_series_anomalies": time_series,
            "top_risky_ips": top_risky_ips,
            "recent_incidents": recent
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/agent-logs")
async def get_agent_logs(
    tenant: TenantContext = Depends(get_tenant_context),
    incident_id: Optional[str] = None,
    limit: int = Query(default=50, le=200)
):
    """Get agent decision logs for the tenant"""
    try:
        if incident_id:
            incident = tenant_es_service.get_incident(tenant, incident_id)
            if incident:
                return {"logs": incident.get('agent_logs', [])}
            return {"logs": []}

        incidents = tenant_es_service.get_incidents(tenant, limit=limit)
        all_logs = []
        for inc in incidents:
            logs = inc.get('agent_logs', [])
            for log in logs:
                log['incident_id'] = inc.get('id')
            all_logs.extend(logs)

        all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return {"logs": all_logs[:limit]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Background Detection (Tenant-aware) =============

async def continuous_detection_task(tenant: TenantContext):
    """Background task for continuous anomaly detection for a tenant"""
    global anomaly_detection_running
    anomaly_detection_running = True

    while anomaly_detection_running:
        try:
            end = datetime.utcnow()
            start = end - timedelta(minutes=settings.ANOMALY_WINDOW_MINUTES)

            logs = tenant_es_service.get_logs_window(tenant, start, end)

            if logs and len(logs) >= 10:
                result = anomaly_detector.predict(logs)

                if result.is_anomaly and result.anomaly_score > 0.6:
                    print(f"[Detection] Anomaly detected for org {tenant.org_id}: score={result.anomaly_score:.2f}")

                    incident = process_anomaly(result, logs, tenant_context=tenant.to_dict())
                    incident_id = tenant_es_service.index_incident(tenant, incident)

                    print(f"[Detection] Created incident: {incident_id}")

        except Exception as e:
            print(f"[Detection] Error: {e}")

        await asyncio.sleep(30)


@app.post("/api/detection/start")
async def start_detection(
    background_tasks: BackgroundTasks,
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Start continuous anomaly detection for the tenant"""
    global anomaly_detection_running

    if anomaly_detection_running:
        return {"status": "already_running"}

    background_tasks.add_task(continuous_detection_task, tenant)
    return {"status": "started"}


@app.post("/api/detection/stop")
async def stop_detection(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Stop continuous anomaly detection"""
    global anomaly_detection_running
    anomaly_detection_running = False
    return {"status": "stopped"}


# ============= Simulation (Tenant-aware) =============

@app.post("/api/simulate/attack")
async def simulate_attack(
    tenant: TenantContext = Depends(get_tenant_context),
    scenario: str = Query(..., description="Attack scenario: brute_force, ddos, recon, injection, suspicious, http_anomaly, mixed")
):
    """Simulate an attack scenario for the tenant"""
    import subprocess
    import os

    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scripts", "log_generator.py"
    )

    try:
        result = subprocess.run(
            ["python3", script_path, "-m", "attack", "-s", scenario],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

        return {
            "status": "success",
            "scenario": scenario,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Evaluation (Tenant-aware) =============

@app.get("/api/evaluation/run")
async def run_evaluation(
    tenant: TenantContext = Depends(get_tenant_context),
    mode: str = Query(default="holdout", description="Evaluation mode"),
    samples: int = Query(default=100, ge=20, le=500),
    attack_ratio: float = Query(default=0.1, ge=0.05, le=0.5)
):
    """Run performance evaluation"""
    try:
        from ml.evaluation import evaluator

        if mode == "holdout":
            metrics = evaluator.evaluate_with_holdout(
                num_test_samples=samples,
                attack_ratio=attack_ratio
            )
        elif mode == "elasticsearch_holdout":
            metrics = evaluator.evaluate_from_elasticsearch_holdout(
                train_hours=24,
                test_hours=6,
                gap_hours=1
            )
        elif mode == "cross_validation":
            cv_results = evaluator.evaluate_with_cross_validation(
                num_folds=5,
                num_samples=samples,
                attack_ratio=attack_ratio
            )
            from backend.models.schemas import EvaluationMetrics
            metrics = EvaluationMetrics(**cv_results['fold_metrics'][0])
            evaluator.save_results(metrics, name=mode)
            return {
                "metrics": metrics.model_dump(),
                "cross_validation": {
                    "f1_mean": cv_results['f1_mean'],
                    "f1_std": cv_results['f1_std'],
                    "precision_mean": cv_results['precision_mean'],
                    "precision_std": cv_results['precision_std'],
                    "recall_mean": cv_results['recall_mean'],
                    "recall_std": cv_results['recall_std'],
                    "num_folds": cv_results['num_folds']
                }
            }
        else:
            metrics = evaluator.evaluate_with_holdout(
                num_test_samples=samples,
                attack_ratio=attack_ratio
            )

        evaluator.save_results(metrics, name=mode)

        return {"metrics": metrics.model_dump()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/evaluation/results")
async def get_evaluation_results(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get historical evaluation results"""
    try:
        from ml.evaluation import evaluator
        results = evaluator.load_results()
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============= Demo/Testing (Tenant-aware) =============

@app.delete("/api/demo/clear-data")
async def clear_demo_data(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Clear all demo data from tenant's indices"""
    try:
        deleted_incidents = 0
        deleted_anomalies = 0

        try:
            result = tenant_es_service.es.delete_by_query(
                index=tenant.incidents_index,
                query={"match_all": {}},
                refresh=True
            )
            deleted_incidents = result.get('deleted', 0)
        except Exception as e:
            logger.warning(f"[Demo] Error clearing incidents: {e}")

        try:
            result = tenant_es_service.es.delete_by_query(
                index=tenant.anomalies_index,
                query={"match_all": {}},
                refresh=True
            )
            deleted_anomalies = result.get('deleted', 0)
        except Exception as e:
            logger.warning(f"[Demo] Error clearing anomalies: {e}")

        return {
            "status": "success",
            "deleted_incidents": deleted_incidents,
            "deleted_anomalies": deleted_anomalies
        }
    except Exception as e:
        logger.error(f"[Demo] Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/demo/create-sample-incidents")
async def create_sample_incidents(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Create sample incidents for demonstration purposes for the tenant"""
    import random
    from backend.models.schemas import AnomalyResult, AnomalyFeatures, Incident, ThreatClassification, RecommendedAction

    risky_ip_pool = ["10.0.1.100", "192.168.1.50", "172.16.0.25", "10.0.2.200", "192.168.2.75"]

    sample_attacks = [
        ("RECONNAISSANCE", "LOW", "Minor port scanning activity"),
        ("ANOMALOUS_TRAFFIC", "LOW", "Unusual traffic pattern detected"),
        ("AUTH_FAILURE", "LOW", "Single failed login attempt"),
        ("BRUTE_FORCE", "MEDIUM", "Multiple failed login attempts"),
        ("RECONNAISSANCE", "MEDIUM", "Port scanning with multiple probes"),
        ("SUSPICIOUS_IP", "MEDIUM", "Traffic from suspicious IP range"),
        ("SQL_INJECTION", "HIGH", "SQL injection attempt in query"),
        ("XSS", "HIGH", "Cross-site scripting attempt detected"),
        ("BRUTE_FORCE", "HIGH", "Sustained brute force attack"),
        ("DDOS", "CRITICAL", "High volume DDoS attack"),
        ("INJECTION", "CRITICAL", "Command injection in API"),
        ("SQL_INJECTION", "CRITICAL", "Successful SQL injection with data access"),
    ]

    created_incidents = []
    now = datetime.utcnow()

    # Create anomalies for time series
    for i in range(12):
        minutes_ago = i * 10
        anomaly_time = now - timedelta(minutes=minutes_ago)
        source_ip = random.choice(risky_ip_pool)

        anomaly = AnomalyResult(
            timestamp=anomaly_time,
            anomaly_score=random.uniform(0.5, 0.9),
            is_anomaly=random.random() > 0.3,
            features=AnomalyFeatures(
                ip_frequency=random.uniform(5, 20),
                failed_login_ratio=random.uniform(0.1, 0.6),
                time_deviation=random.uniform(0.1, 0.4),
                status_code_entropy=random.uniform(0.2, 0.6),
                request_burst_rate=random.uniform(5, 25),
                geo_anomaly_score=random.uniform(0.1, 0.5),
                unique_paths_ratio=random.uniform(0.2, 0.7),
                avg_latency=random.uniform(50, 300),
                error_rate=random.uniform(0.05, 0.3)
            ),
            source_ips=[source_ip],
            affected_paths=["/api/login", "/api/users"],
            window_start=anomaly_time - timedelta(minutes=5),
            window_end=anomaly_time
        )
        tenant_es_service.index_anomaly(tenant, anomaly)

    # Create incidents
    for idx, (attack_type, severity, description) in enumerate(sample_attacks):
        try:
            hours_ago = (idx / len(sample_attacks)) * 4
            incident_time = now - timedelta(hours=hours_ago)
            source_ip = random.choice(risky_ip_pool)

            anomaly = AnomalyResult(
                timestamp=incident_time,
                anomaly_score=random.uniform(0.6, 0.95),
                is_anomaly=True,
                features=AnomalyFeatures(
                    ip_frequency=random.uniform(5, 20),
                    failed_login_ratio=random.uniform(0.3, 0.8),
                    time_deviation=random.uniform(0.1, 0.5),
                    status_code_entropy=random.uniform(0.2, 0.8),
                    request_burst_rate=random.uniform(5, 30),
                    geo_anomaly_score=random.uniform(0.1, 0.6),
                    unique_paths_ratio=random.uniform(0.3, 0.9),
                    avg_latency=random.uniform(50, 500),
                    error_rate=random.uniform(0.1, 0.5)
                ),
                source_ips=[source_ip],
                affected_paths=["/api/login", "/api/admin", "/api/users"],
                window_start=incident_time - timedelta(minutes=5),
                window_end=incident_time
            )

            tenant_es_service.index_anomaly(tenant, anomaly)

            classification = ThreatClassification(
                attack_type=attack_type,
                severity=severity,
                confidence=random.uniform(0.7, 0.95),
                indicators=[description],
                mitre_techniques=["T1110", "T1078"]
            )

            recommended_action = RecommendedAction(
                action_type="BLOCK_IP" if severity in ["HIGH", "CRITICAL"] else "RATE_LIMIT",
                target=anomaly.source_ips[0] if anomaly.source_ips else "unknown",
                reasoning=f"Automated response to {attack_type}: {description}",
                confidence=random.uniform(0.7, 0.9)
            )

            status_options = [
                IncidentStatus.PENDING_APPROVAL,
                IncidentStatus.APPROVED,
                IncidentStatus.EXECUTED,
                IncidentStatus.RESOLVED,
            ]
            incident_status = random.choice(status_options)

            incident = Incident(
                anomaly=anomaly,
                classification=classification,
                selected_action=recommended_action,
                status=incident_status,
                created_at=incident_time,
                updated_at=incident_time
            )

            incident_id = tenant_es_service.index_incident(tenant, incident)
            created_incidents.append({
                "id": incident_id,
                "type": attack_type,
                "severity": severity,
                "status": incident_status.value,
                "source_ip": source_ip
            })

        except Exception as e:
            logger.error(f"[Demo] Failed to create sample incident: {e}")

    severity_counts = {}
    status_counts = {}
    for inc in created_incidents:
        sev = inc['severity']
        sta = inc['status']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        status_counts[sta] = status_counts.get(sta, 0) + 1

    return {
        "status": "success",
        "created_incidents": len(created_incidents),
        "created_anomalies": 12,
        "severity_distribution": severity_counts,
        "status_distribution": status_counts,
        "incidents": created_incidents
    }


# ============= Learning & Autonomy (Tenant-aware) =============

@app.get("/api/learning/stats")
async def get_learning_stats(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Get learning system statistics"""
    from agents.memory import agent_memory
    from agents.decision_agent import decision_agent

    return {
        "memory_stats": agent_memory.get_learning_stats(),
        "decision_stats": decision_agent.get_stats(),
        "autonomous_mode": settings.AUTONOMOUS_MODE if hasattr(settings, 'AUTONOMOUS_MODE') else True,
        "human_in_loop": settings.HUMAN_IN_LOOP_ENABLED
    }


@app.post("/api/learning/feedback")
async def submit_feedback(
    tenant: TenantContext = Depends(get_tenant_context),
    incident_id: str = Query(...),
    was_correct: bool = Query(...),
    was_false_positive: bool = Query(default=False),
    was_false_negative: bool = Query(default=False),
    feedback: Optional[str] = Query(default=None)
):
    """Submit feedback on an incident for learning"""
    from agents.memory import agent_memory

    agent_memory.record_outcome(
        decision_id=incident_id,
        success=was_correct,
        feedback=feedback,
        was_false_positive=was_false_positive,
        was_false_negative=was_false_negative
    )

    return {
        "status": "success",
        "message": "Feedback recorded for learning",
        "updated_stats": agent_memory.get_learning_stats()
    }


@app.get("/api/autonomy/status")
async def get_autonomy_status(
    current_user: User = Depends(get_current_user)
):
    """Get current autonomy configuration and stats"""
    from agents.decision_agent import decision_agent
    from agents.memory import agent_memory

    stats = decision_agent.get_stats()
    memory_stats = agent_memory.get_learning_stats()

    return {
        "autonomous_mode": getattr(settings, 'AUTONOMOUS_MODE', True),
        "human_in_loop_enabled": settings.HUMAN_IN_LOOP_ENABLED,
        "auto_approve_threshold": memory_stats.get('auto_approve_threshold', 0.75),
        "total_decisions": stats.get('total_decisions', 0),
        "auto_approved": stats.get('auto_approved', 0),
        "auto_approve_rate": stats.get('auto_approve_rate', 0),
        "recent_accuracy": memory_stats.get('recent_accuracy', 0),
        "learned_thresholds": memory_stats.get('learned_thresholds', {}),
        "false_positives": memory_stats.get('false_positives', 0),
        "false_negatives": memory_stats.get('false_negatives', 0)
    }


@app.post("/api/demo/autonomous-incident")
async def create_autonomous_incident(
    tenant: TenantContext = Depends(get_tenant_context)
):
    """Create and auto-execute a sample incident for the tenant"""
    import random
    from agents.workflow import soc_workflow, process_anomaly
    from ml.anomaly_detector import anomaly_detector

    attack_type = random.choice(["BRUTE_FORCE", "DDOS", "RECONNAISSANCE"])
    severity = random.choice(["MEDIUM", "HIGH"])

    try:
        fake_logs = []
        base_ip = f"10.0.{random.randint(1, 255)}.{random.randint(1, 255)}"
        for i in range(50):
            fake_logs.append({
                "@timestamp": utc_isoformat(),
                "client_ip": base_ip,
                "method": "POST" if attack_type == "BRUTE_FORCE" else "GET",
                "path": "/api/login" if attack_type == "BRUTE_FORCE" else f"/api/path{i}",
                "status_code": 401 if attack_type == "BRUTE_FORCE" and i % 3 == 0 else 200,
                "latency_ms": random.randint(10, 500),
            })

        anomaly_result = anomaly_detector.predict(fake_logs)
        anomaly_result.is_anomaly = True
        anomaly_result.anomaly_score = random.uniform(0.7, 0.95)
        anomaly_result.source_ips = [base_ip]

        incident = process_anomaly(anomaly_result, fake_logs, tenant_context=tenant.to_dict())
        incident_id = tenant_es_service.index_incident(tenant, incident)

        return {
            "status": "success",
            "incident_id": incident_id,
            "attack_type": incident.classification.attack_type.value if incident.classification else "UNKNOWN",
            "severity": incident.classification.severity.value if incident.classification else "UNKNOWN",
            "action_taken": incident.selected_action.action_type.value if incident.selected_action else "NONE",
            "auto_executed": incident.status == IncidentStatus.EXECUTED,
            "confidence": incident.classification.confidence if incident.classification else 0,
            "reasoning": incident.selected_action.reasoning if incident.selected_action else "N/A"
        }

    except Exception as e:
        logger.error(f"[Demo] Failed to create autonomous incident: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
