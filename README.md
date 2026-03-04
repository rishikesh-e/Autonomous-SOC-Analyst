# Autonomous SOC Analyst

An AI-powered Security Operations Center that autonomously detects, classifies, and responds to security threats using LangGraph agents, Groq LLM (Llama 3.3 70B), and machine learning - with multi-tenant support and human-in-the-loop approval for critical actions.

## Architecture

```
                              LOG SOURCES
                    (Application Logs, Web Server Logs)
                                    |
                                    v
+---------------+     +---------------+     +---------------------------+
| Log Generator |---->|  Fluent Bit   |---->|      Elasticsearch        |
| (Real-time)   |     |  (Parser)     |     |  soc-logs-YYYY.MM.DD      |
+---------------+     +---------------+     |  soc-incidents-{org_id}   |
                                            |  soc-anomalies-{org_id}   |
                                            +-------------+-------------+
                                                          |
+---------------+     +-------------------------------+   |
|   React UI    |<--->|        FastAPI Backend        |<--+
| - Dashboard   |     |  - JWT Authentication         |
| - Incidents   |     |  - Multi-Tenant (Org-scoped)  |
| - Actions     |     |  - WebSocket Real-time        |
| - ML Metrics  |     |  - Role-based Access          |
+---------------+     +---------------+---------------+
                                      |
                      +---------------+---------------+
                      |                               |
              +-------v--------+         +-----------v-----------+
              |  ML Detector   |         |  LangGraph Workflow   |
              | Isolation Forest         |                       |
              | 9 Features     |         |  1. Log Analysis      |
              | Rule Fallback  |         |  2. Threat Classify   |
              +----------------+         |  3. Decision (LLM)    |
                                         |  4. Response          |
                                         |                       |
                                         |  + Learning Memory    |
                                         +-----------------------+
```

## Features

- **Multi-Tenant Architecture**: Organization-scoped data isolation with role-based access
- **JWT Authentication**: Secure API with OWNER/ADMIN/ANALYST/VIEWER roles
- **Organization Invitations**: Invite users via email with role assignment
- **LLM-Powered Agents**: Groq Llama 3.3 70B for intelligent threat analysis
- **ML Anomaly Detection**: Isolation Forest with 9 engineered features
- **4-Agent Workflow**: Log Analysis -> Threat Classification -> Decision -> Response
- **Auto-Approval**: High-confidence decisions execute automatically
- **Learning System**: Improves from past decisions and analyst feedback
- **Real-Time Dashboard**: WebSocket updates, incident management, time-series graphs
- **MITRE ATT&CK Mapping**: Standard threat technique classification

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + JWT Auth |
| Agents | LangGraph (4-agent workflow) |
| LLM | Groq (Llama 3.3 70B Versatile) |
| ML | scikit-learn (Isolation Forest) |
| Storage | Elasticsearch (multi-tenant indices) |
| Ingestion | Fluent Bit |
| Frontend | React + TypeScript + Vite + Tailwind |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Elasticsearch 8.x
- Fluent Bit (optional)
- Groq API Key ([get one free](https://console.groq.com/))

### Setup

```bash
# 1. Clone and setup
cd Autonomous-SOC-Analyst
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your GROQ_API_KEY

# 2. Start Elasticsearch
sudo systemctl start elasticsearch

# 3. Start Backend API
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Start Frontend (new terminal)
cd frontend && npm install && npm run dev

# 5. Start Log Generator (new terminal, optional)
python scripts/log_generator.py -m continuous -r 10 -p 0.15

# 6. Open http://localhost:5173
```

### First Time Setup

```bash
# Register a new user (creates user + organization)
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "username": "admin", "password": "securepass123"}'

# Login to get JWT token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "securepass123"}' | jq -r '.access_token')

# Train the ML model
curl -X POST "http://localhost:8000/api/anomaly/train?hours=1" \
  -H "Authorization: Bearer $TOKEN"

# Run detection
curl -X POST "http://localhost:8000/api/incidents/process?window_minutes=5" \
  -H "Authorization: Bearer $TOKEN"
```

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register new user (creates org) |
| `/api/auth/login` | POST | Login and get JWT token |
| `/api/auth/me` | GET | Get current user info |

### Organization Management
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/organizations/current` | GET | Get current organization |
| `/api/organizations/members` | GET | List organization members |
| `/api/organizations/invite` | POST | Invite user to organization |
| `/api/organizations/invite/{token}/accept` | POST | Accept invitation |

### Detection & Incidents
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/anomaly/train` | POST | Train ML model on logs |
| `/api/anomaly/detect` | POST | Run anomaly detection |
| `/api/incidents/process` | POST | Full detection pipeline |
| `/api/incidents` | GET | List all incidents |
| `/api/incidents/{id}/approve` | POST | Approve/deny incident |
| `/api/detection/start` | POST | Start continuous detection |

### Dashboard & Actions
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/metrics` | GET | Dashboard metrics |
| `/api/actions/blocked-ips` | GET | List blocked IPs |
| `/api/ws/dashboard?token=JWT` | WS | Real-time WebSocket |

## Agent Workflow

```
+------------------+     +----------------------+     +------------------+
| 1. Log Analysis  |---->| 2. Threat Classify   |---->| 3. Decision      |
|                  |     |                      |     |                  |
| - Parse logs     |     | - Attack type        |     | - LLM reasoning  |
| - Extract metrics|     | - Severity level     |     | - Action select  |
| - LLM insights   |     | - MITRE ATT&CK       |     | - Auto-approve?  |
+------------------+     +----------------------+     +--------+---------+
                                                               |
                         +----------------------+              |
                         | 4. Response Agent    |<-------------+
                         |                      |
                         | - Execute action     |
                         | - Record outcome     |
                         | - Update memory      |
                         +----------------------+
```

**Attack Types Detected:**
- BRUTE_FORCE, RECONNAISSANCE, DDOS, INJECTION
- SUSPICIOUS_IP, AUTH_FAILURE, ANOMALOUS_TRAFFIC, XSS

**Actions Available:**
- BLOCK_IP, RATE_LIMIT, ALERT, ESCALATE, MONITOR, NO_ACTION

## Organization Roles

| Role | Permissions |
|------|-------------|
| OWNER | Full access, manage org, delete org |
| ADMIN | Manage members, approve all incidents |
| ANALYST | View incidents, approve assigned |
| VIEWER | Read-only dashboard access |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key (required) | - |
| `GROQ_MODEL` | LLM model | `llama-3.3-70b-versatile` |
| `JWT_SECRET_KEY` | JWT signing secret | Change in production! |
| `ELASTICSEARCH_HOST` | Elasticsearch URL | `http://localhost:9200` |
| `HUMAN_IN_LOOP_ENABLED` | Require approval for all | `false` |
| `AUTO_APPROVE_CONFIDENCE_THRESHOLD` | Auto-approve threshold | `0.75` |

## Project Structure

```
Autonomous-SOC-Analyst/
├── agents/                 # LangGraph agent implementations
│   ├── workflow.py         # 4-agent orchestration
│   ├── log_analysis_agent.py
│   ├── threat_classification_agent.py
│   ├── decision_agent.py   # LLM-powered decisions
│   ├── response_agent.py   # Action execution
│   └── memory.py           # Learning system
├── backend/
│   ├── api/main.py         # FastAPI endpoints
│   ├── auth/               # JWT auth, users, organizations
│   ├── models/schemas.py   # Pydantic models
│   └── services/           # Elasticsearch service
├── ml/
│   ├── anomaly_detector.py # Isolation Forest
│   ├── feature_engineering.py
│   └── evaluation.py       # Model evaluation
├── frontend/               # React + TypeScript dashboard
├── config/settings.py      # Configuration
├── scripts/log_generator.py # Test log generation
├── fluent-bit/             # Log ingestion config
└── logs/                   # Application logs
```

## Production Notes

**Defensive actions are simulated.** The system stores blocked IPs in memory but does not actually block network traffic. For production:
- Integrate with iptables/nftables (Linux)
- AWS WAF, Cloudflare, Azure NSG (Cloud)
- Palo Alto, Fortinet APIs (Enterprise)

## Troubleshooting

```bash
# Check Elasticsearch
curl http://localhost:9200/_cluster/health?pretty

# Check API status
curl http://localhost:8000/api/status

# Check log count
curl "http://localhost:9200/soc-logs*/_count"

# Test Groq API
python -c "from groq import Groq; print(Groq().chat.completions.create(model='llama-3.3-70b-versatile', messages=[{'role':'user','content':'hi'}]).choices[0].message.content)"
```
