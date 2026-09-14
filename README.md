# Autonomous Multi-Agent AI Research Platform
### Enterprise Security Perimeter • pgvector Semantic Caching • Redis Streams • PyRIT Red Teaming

A production-grade multi-agent autonomous research platform with a 4-agent LangGraph pipeline (**Search → Summarize → Write → Verify**), dual-boundary AWS Bedrock Guardrails, pgvector semantic caching (<15ms), Redis STM + Streams event telemetry, and a decoupled PyRIT adversarial stress-testing harness with an interactive split-screen Adversarial War Room dashboard.

---

## 1. Architectural Architecture & Key Tenets

```
               ┌─────────────────────────────────────────────────────────┐
               │         Client Browser / Adversarial War Room           │
               └────────────┬─────────────────────────────▲──────────────┘
                            │ POST /api/v1/research       │ Lossless SSE
                            ▼                             │ (Redis Streams)
┌─────────────────────────────────────────────────────────┴──────────────┐
│ FastAPI Ingress Gateway                                                │
│                                                                        │
│   [1. Bedrock Guardrail: Ingress Boundary]                             │
│       ├── Intercept Prompt Injections & Malicious Policy Overrides     │
│       └── Boto3 Mock Engine for Zero-Cloud Offline Development         │
│                                                                        │
│   [2. PostgreSQL pgvector Semantic Cache (<12ms)]                      │
│       ├── FastEmbed ONNX (BAAI/bge-small-en-v1.5, 384-dim)             │
│       ├── HNSW Index (vector_cosine_ops, threshold >= 0.95)            │
│       └── Write Gate: verification_score >= 0.90 && !is_degraded       │
└───────────────────────────┬────────────────────────────────────────────┘
                            │ (Cache Miss)
                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LangGraph Deterministic 4-Agent Pipeline                               │
│                                                                        │
│  [Node 1: Search Agent]                                                │
│    ├── DuckDuckGo / Tavily sub-query expansion (3 targeted queries)    │
│    ├── Deterministic text scrubbing (<3,000 chars per source)          │
│    └── XPIA Quarantine & <untrusted_source id="..."> XML encapsulation │
│           │                                                            │
│           ▼                                                            │
│  [Node 2: Summarize Agent]                                             │
│    └── Outline synthesis preserving factual citation references        │
│           │                                                            │
│           ▼                                                            │
│  [Node 3: Write Agent] ◄──────────────────────┐ (Retry Loopback)       │
│    └── Structured Report (Summary, Deep Dive, │ Claims Audit Feedback │
│        Empirical Findings, Citations)          │ (if score < 0.85 &     │
│           │                                   │  iteration < 2)        │
│           ▼                                   │                        │
│  [Node 4: Verify Agent] ──────────────────────┘                        │
│    ├── Empirical claim extraction & source quote verification          │
│    └── Computes verification_score = supported / total                 │
│           │                                                            │
│           ├─ score >= 0.85 ─────────► [Node 6: Egress Guardrail]       │
│           └─ score < 0.85 & iter >= 2 ► [Node 5: Degraded Export]      │
│                                              │                         │
│                                              ▼                         │
│                                        [Node 6: Egress Guardrail]      │
│                                              ├── PII Anonymization     │
│                                              ├── PostgreSQL LTM Commit │
│                                              └── FastEmbed Cache Store │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hardened Review Invariants

1. **Unified Vector Layer in PostgreSQL (`pgvector`)**: Standard AWS ElastiCache for Redis does not support RediSearch (`FT.CREATE`). Both Tier 2 Semantic Cache and Tier 3 LTM are stored in PostgreSQL with HNSW vector indexing (`vector_cosine_ops`). Redis is strictly Tier 1 STM and Redis Streams.
2. **Lossless Event Telemetry via Redis Streams**: Raw Pub/Sub is replaced with Redis Streams (`XADD`/`XREAD`) with `Last-Event-ID` support, ensuring zero event loss across SSE client reconnects.
3. **Decoupled PyRIT Red Teaming**: Conversational attacks (Crescendo, Skeleton Key, Jailbreak) evaluate directly against the Bedrock Ingress Guardrail & LLM target; XPIA attacks evaluate against the Agent Target with controlled synthetic search fixtures.
4. **Pure-Python Exports**: PDF generation is built on `fpdf2`, eliminating unstable native C DLL dependencies (Pango/Cairo) while providing publication-ready formatting.
5. **Zero-Cloud Offline Parity**: High-fidelity local mock engine mirrors AWS Boto3 `ApplyGuardrailResponseTypeDef` schemas, enabling full pipeline testing with zero external credentials.

---

## 3. Quickstart (1-Command Local Evaluation)

### Option A: Docker Compose (Full Stack)
```bash
docker compose up --build
```
Open **`http://localhost:8000`** to access the live split-screen Adversarial War Room cockpit.

### Option B: Local Development
```bash
# 1. Install dependencies
pip install .

# 2. Run test suite
pytest tests/ -v

# 3. Start local web server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/research` | Submit research topic (evaluates ingress guardrail & pgvector cache) |
| `GET` | `/api/v1/research/stream/{session_id}` | Lossless SSE stream for agent DAG progress (supports `Last-Event-ID`) |
| `GET` | `/api/v1/research/status/{session_id}` | Query current pipeline state and final report |
| `GET` | `/api/v1/research/export/{session_id}?format=markdown\|json\|pdf` | Export verified report in MD, JSON, or pure-Python PDF |
| `POST` | `/api/v1/redteam/campaigns` | Launch asynchronous PyRIT attack campaign (`crescendo`, `skeleton_key`, `jailbreak`, `xpia`) |
| `GET` | `/api/v1/redteam/stream/{campaign_id}` | SSE stream for real-time attack turns and guardrail block telemetry |
| `GET` | `/api/v1/redteam/campaigns/{campaign_id}` | Retrieve campaign scorecard and audit logs |
| `GET` | `/health` / `/ready` / `/metrics` | Liveness, readiness probes, and operational telemetry |

---

## 5. AWS Terraform Deployment

The `terraform/` directory contains complete modular infrastructure with a single-AZ dev cost profile ($0 idle NAT Gateway fees) and multi-AZ production parity:

```bash
cd terraform
terraform init
terraform plan -var="environment=dev" -var="single_az_dev=true"
terraform apply
```

Resources provisioned:
- **VPC & Subnets**: Single-AZ dev or Multi-AZ prod with internet gateway.
- **Aurora PostgreSQL Serverless v2**: `pgvector` enabled via parameter group.
- **ElastiCache Redis**: Micro instance for Redis STM and Redis Streams.
- **AWS Bedrock Guardrail**: High-strength content filters, PII anonymization, and prompt attack interception.
- **ECS Fargate & ALB**: Containerized service running behind an Application Load Balancer.
- **EventBridge**: Weekly scheduled automated red-team audit task.

---

## 6. Verification & Test Suite

Run the full pytest suite:
```bash
pytest tests/ -v
```

Test coverage includes:
- `tests/unit/test_guardrails.py`: Bedrock mock engine, PII masking, and XML boundary encapsulation.
- `tests/unit/test_semantic_cache.py`: FastEmbed ONNX embedding, cosine similarity, and cache write gates.
- `tests/unit/test_agents.py`: Search, summarize, write, verify, and degraded export nodes.
- `tests/unit/test_gateway.py`: Multi-provider failover routing and circuit breaker tripping.
- `tests/integration/test_pipeline_e2e.py`: Full research execution from topic to verified PDF export.
- `tests/integration/test_pyrit_attacks.py`: Decoupled Crescendo, Skeleton Key, and XPIA red team runs.
- `tests/integration/test_api_routes.py`: FastAPI endpoints, SSE headers, and error handling.
