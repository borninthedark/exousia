# BlazingMQ Integration Guide

## Overview

Exousia now uses **Bloomberg's BlazingMQ** as its message queue for idempotent, immutable build operations. This provides:

- ✅ **Idempotency**: Automatic message deduplication prevents duplicate builds
- ✅ **Immutability**: Event sourcing pattern for complete audit trail
- ✅ **Reliability**: At-least-once delivery with dead letter queue
- ✅ **Scalability**: Horizontal scaling for both laptop and cloud deployments
- ✅ **Performance**: Low-latency message delivery (microsecond range)

## Architecture

### Dual-Mode Design

Exousia supports two deployment modes, optimized for different use cases:

| Feature | Laptop Mode | Cloud Mode |
|---------|-------------|------------|
| **Database** | SQLite (shared volume) | PostgreSQL (managed service) |
| **BlazingMQ** | Single broker | 3-node cluster (HA) |
| **API Replicas** | 1 pod (sidecar) | 3-10 pods (auto-scaling) |
| **Workers** | 1 sidecar container | 2-20 pods (HPA based on queue depth) |
| **Message Dedup** | In-memory + BlazingMQ | BlazingMQ distributed |
| **Cost** | Free (local resources) | Optimized for cloud pricing |
| **Deployment** | Podman Compose | Kubernetes |

### Container Architecture

#### Option 1: Sidecar Pattern (Recommended for Laptop Mode)

```
┌─────────────────────────────────────┐
│           Kubernetes Pod            │
├─────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐ │
│  │              │  │              │ │
│  │  FastAPI     │  │  Build       │ │
│  │  Container   │  │  Worker      │ │
│  │  (Port 8000) │  │  (Sidecar)   │ │
│  │              │  │              │ │
│  └──────┬───────┘  └──────┬───────┘ │
│         │                 │         │
│         └────────┬────────┘         │
│                  │                  │
│         ┌────────▼────────┐         │
│         │  Shared Volume  │         │
│         │  (SQLite DB +   │         │
│         │   Temp Files)   │         │
│         └─────────────────┘         │
└─────────────────────────────────────┘
           │
           │ tcp://localhost:30114
           ▼
    ┌──────────────┐
    │  BlazingMQ   │
    │   Broker     │
    └──────────────┘
```

**Benefits**:
- Shared filesystem (no network for DB access)
- Localhost BlazingMQ connection (low latency)
- Single pod deployment (resource efficient)
- Perfect for laptop/development environments

#### Option 2: Microservices Pattern (Recommended for Cloud Mode)

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│  API Pod   │  │  API Pod   │  │  API Pod   │
│  Replica 1 │  │  Replica 2 │  │  Replica 3 │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │
      └───────────────┴───────────────┘
                      │
                      │ tcp://blazingmq-0:30114
                      ▼
       ┌──────────────────────────────┐
       │  BlazingMQ Cluster (HA)      │
       │  ┌────────┬────────┬────────┐│
       │  │ Node 0 │ Node 1 │ Node 2 ││
       │  └────────┴────────┴────────┘│
       └──────────────────────────────┘
                      │
                      │
      ┌───────────────┴───────────────┐
      │               │               │
┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐
│  Worker    │  │  Worker    │  │  Worker    │
│  Pod 1     │  │  Pod 2     │  │  Pod 3     │
└────────────┘  └────────────┘  └────────────┘
```

**Benefits**:
- Independent scaling of API and workers
- High availability (3-node BlazingMQ cluster)
- Load balancing across replicas
- Auto-scaling based on queue depth

### Message Flow with Idempotency

```
1. User triggers build (POST /builds/trigger)
   ↓
2. API creates BuildModel (status: QUEUED)
   ↓
3. API creates QueueMessage with deterministic ID
   Message ID = SHA256(message_type + payload)
   ↓
4. API enqueues message to BlazingMQ
   - BlazingMQ deduplicates via message GUID
   - Returns False if duplicate (idempotent!)
   ↓
5. API returns 202 Accepted immediately
   ↓
6. Worker dequeues message from BlazingMQ
   ↓
7. Worker checks build status (idempotency)
   - If status != QUEUED, skip (already processed)
   ↓
8. Worker creates immutable BuildEvent
   - Event type: "build_started"
   - From: QUEUED, To: IN_PROGRESS
   ↓
9. Worker triggers GitHub workflow
   ↓
10. Worker enqueues status check message
   ↓
11. Status check worker polls GitHub
   ↓
12. On completion, creates final BuildEvent
   - Event type: "build_completed"
   - From: IN_PROGRESS, To: SUCCESS/FAILURE
```

## Deployment

### Laptop Mode (Podman Compose)

#### Prerequisites

```bash
# Install podman and podman-compose
sudo dnf install podman podman-compose

# Install Python dependencies
pip install -r api/requirements.txt
```

#### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/borninthedark/exousia.git
cd exousia

# 2. Set environment variables
cat > .env << EOF
DEPLOYMENT_MODE=laptop
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPO=borninthedark/exousia
BLAZINGMQ_ENABLED=true
EOF

# 3. Start BlazingMQ + API + Worker (sidecar mode)
podman-compose -f podman-compose.blazingmq.yml up -d

# 4. Check logs
podman-compose -f podman-compose.blazingmq.yml logs -f

# 5. Access API
curl http://localhost:8000/health

# 6. Trigger a build
curl -X POST http://localhost:8000/builds/trigger \
  -H "Content-Type: application/json" \
  -d '{"config_id": 1, "ref": "main"}'

# 7. Check build status
curl http://localhost:8000/builds/1
```

#### Stopping

```bash
# Stop services
podman-compose -f podman-compose.blazingmq.yml down

# Clean up data (WARNING: deletes database and queues)
podman-compose -f podman-compose.blazingmq.yml down -v
```

### Cloud Mode (Kubernetes)

#### Prerequisites

```bash
# Install kubectl and helm
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify cluster access
kubectl cluster-info
```

#### Deployment Options

##### Option 1: Sidecar Architecture (Simple)

```bash
# 1. Create namespace
kubectl create namespace exousia

# 2. Create secrets
kubectl create secret generic exousia-secrets \
  --from-literal=github-token=ghp_your_token \
  --from-literal=database-url=postgresql+asyncpg://... \
  --from-literal=secret-key=$(openssl rand -hex 32) \
  -n exousia

# 3. Deploy BlazingMQ cluster
kubectl apply -f k8s/blazingmq/blazingmq-statefulset.yaml

# 4. Wait for BlazingMQ to be ready
kubectl wait --for=condition=ready pod -l app=blazingmq -n exousia --timeout=300s

# 5. Deploy sidecar architecture
kubectl apply -f k8s/exousia-sidecar-deployment.yaml

# 6. Get service URL
kubectl get svc exousia -n exousia
```

##### Option 2: Microservices Architecture (Scalable)

```bash
# 1-3. Same as above

# 4. Deploy microservices
kubectl apply -f k8s/exousia-deployment.yaml

# 5. Check deployment
kubectl get pods -n exousia
kubectl get hpa -n exousia  # Check auto-scaling
```

#### Monitoring

```bash
# Check BlazingMQ metrics (if Prometheus enabled)
kubectl port-forward -n exousia svc/blazingmq 9091:9091
curl http://localhost:9091/metrics

# Check pod logs
kubectl logs -f -n exousia deployment/exousia-api
kubectl logs -f -n exousia deployment/exousia-worker

# Check queue depth
kubectl exec -it -n exousia blazingmq-0 -- bmqstoragetool summary
```

## Configuration

### Environment Variables

| Variable | Laptop Default | Cloud Default | Description |
|----------|----------------|---------------|-------------|
| `DEPLOYMENT_MODE` | `laptop` | `cloud` | Deployment mode |
| `BLAZINGMQ_ENABLED` | `true` | `true` | Enable BlazingMQ |
| `BLAZINGMQ_BROKER_URI` | `tcp://localhost:30114` | `tcp://blazingmq-0.blazingmq:30114` | Broker URI |
| `BLAZINGMQ_DOMAIN` | `exousia` | `exousia` | Queue domain |
| `BLAZINGMQ_QUEUE_BUILD` | `build.queue` | `build.queue` | Build queue name |
| `BLAZINGMQ_QUEUE_DLQ` | `build.dlq` | `build.dlq` | Dead letter queue |
| `QUEUE_MAX_RETRIES` | `3` | `3` | Max retry attempts |
| `QUEUE_RETRY_DELAY` | `60` | `60` | Retry delay (seconds) |
| `WORKER_CONCURRENCY` | `1` | `4` | Worker threads |
| `DATABASE_URL` | `sqlite+aiosqlite:///./exousia.db` | `postgresql+asyncpg://...` | Database URL |

### BlazingMQ Queues

#### `build.queue` (Priority Queue)
- **Purpose**: Build trigger and status check messages
- **Mode**: Priority
- **Max Retries**: 5
- **Dedup Window**: 5 minutes
- **Consistency**: Strong

#### `build.dlq` (Dead Letter Queue)
- **Purpose**: Failed messages after max retries
- **Mode**: Fanout
- **Max Retries**: 1 (no retry)
- **Consistency**: Strong

## API Usage

### Trigger Build (Idempotent)

```bash
# First call - creates build and enqueues
curl -X POST http://localhost:8000/builds/trigger \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: build-main-$(date +%Y%m%d)" \
  -d '{
    "config_id": 1,
    "ref": "main",
    "image_type": "fedora-sway-atomic",
    "fedora_version": "43"
  }'

# Response: 202 Accepted
{
  "id": 123,
  "status": "queued",
  "message": "Build queued successfully"
}

# Second call (same payload) - returns existing build
# BlazingMQ deduplicates the message automatically
curl -X POST http://localhost:8000/builds/trigger \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: build-main-$(date +%Y%m%d)" \
  -d '{ ... same payload ... }'

# Response: 202 Accepted (same build ID)
{
  "id": 123,
  "status": "in_progress",
  "message": "Build already exists"
}
```

### Check Build Status

```bash
curl http://localhost:8000/builds/123

# Response
{
  "id": 123,
  "status": "in_progress",
  "workflow_run_id": 456,
  "events": [
    {
      "event_type": "build_queued",
      "timestamp": "2025-11-29T10:00:00Z"
    },
    {
      "event_type": "build_started",
      "from_status": "queued",
      "to_status": "in_progress",
      "timestamp": "2025-11-29T10:00:10Z"
    }
  ]
}
```

### View Event History (Immutable Audit Trail)

```bash
curl http://localhost:8000/builds/123/events

# Response: Complete event history
[
  {
    "id": 1,
    "event_type": "build_queued",
    "timestamp": "2025-11-29T10:00:00Z"
  },
  {
    "id": 2,
    "event_type": "build_started",
    "from_status": "queued",
    "to_status": "in_progress",
    "event_data": {"message_id": "abc123"},
    "timestamp": "2025-11-29T10:00:10Z"
  },
  {
    "id": 3,
    "event_type": "workflow_triggered",
    "event_data": {"workflow_run_id": 456},
    "timestamp": "2025-11-29T10:00:15Z"
  },
  {
    "id": 4,
    "event_type": "build_completed",
    "from_status": "in_progress",
    "to_status": "success",
    "timestamp": "2025-11-29T10:15:00Z"
  }
]
```

## Benefits Summary

### Immutability

- ✅ **Event Sourcing**: All state transitions recorded as immutable events
- ✅ **Audit Trail**: Complete history of build lifecycle
- ✅ **No Data Loss**: Events never deleted, only appended
- ✅ **Time Travel**: Can reconstruct state at any point in time

### Idempotency

- ✅ **Message Deduplication**: BlazingMQ deduplicates by message GUID
- ✅ **Idempotent Operations**: Calling same API twice has same effect
- ✅ **Retry Safety**: Workers can safely retry failed operations
- ✅ **Concurrent Safety**: Multiple workers won't duplicate work

### Cost Optimization

| Component | Laptop Cost | Cloud Cost (Optimized) |
|-----------|-------------|------------------------|
| **BlazingMQ** | Free (local) | $30-50/month (3 small VMs or K8s nodes) |
| **Database** | Free (SQLite) | $20-30/month (managed PostgreSQL) |
| **API** | Free | $10-20/month (small instances, auto-scale) |
| **Workers** | Free | $20-40/month (auto-scale 2-20 based on queue) |
| **Total** | **$0** | **$80-140/month** (vs $200+ for traditional microservices) |

**Cost Savings in Cloud**:
- 40-60% cheaper than separate message queue service (AWS SQS/RabbitMQ managed)
- Auto-scaling workers only when queue has messages
- Sidecar option reduces pod overhead
- BlazingMQ is self-hosted (no SaaS fees)

## Troubleshooting

### BlazingMQ Connection Issues

```bash
# Check BlazingMQ broker status
podman ps | grep blazingmq

# Check broker logs
podman logs exousia-blazingmq-broker

# Test connection
nc -zv localhost 30114
```

### Worker Not Processing Messages

```bash
# Check worker logs
kubectl logs -f deployment/exousia-worker -n exousia

# Check queue depth
kubectl exec -it blazingmq-0 -n exousia -- bmqstoragetool summary

# Manual message consumption (debug)
kubectl exec -it deployment/exousia-worker -n exousia -- \
  python -c "
from api.queue import get_queue_backend
import asyncio
async def test():
    q = get_queue_backend()
    await q.connect()
    msg = await q.dequeue('build.queue', timeout=10)
    print(msg)
asyncio.run(test())
"
```

### Dead Letter Queue

```bash
# Check DLQ for failed messages
kubectl exec -it deployment/exousia-worker -n exousia -- \
  python -c "
from api.queue import get_queue_backend
from api.config import settings
import asyncio
async def check_dlq():
    q = get_queue_backend()
    await q.connect()
    msg = await q.dequeue(settings.BLAZINGMQ_QUEUE_DLQ, timeout=5)
    if msg:
        print(f'Failed message: {msg.to_dict()}')
    else:
        print('DLQ is empty')
asyncio.run(check_dlq())
"
```

## Migration from Current System

### Step 1: Add BlazingMQ (Backwards Compatible)

```bash
# Current system continues to work
# BlazingMQ runs alongside existing workflow trigger
```

### Step 2: Gradual Migration

```python
# api/routers/build.py - Dual mode
if settings.BLAZINGMQ_ENABLED:
    # Use queue
    await queue.enqueue(message)
else:
    # Direct workflow trigger (legacy)
    await github.trigger_workflow()
```

### Step 3: Full Cutover

```bash
# Set BLAZINGMQ_ENABLED=true
# All builds use queue
```

## References

- [BlazingMQ Documentation](https://bloomberg.github.io/blazingmq/)
- [BlazingMQ GitHub](https://github.com/bloomberg/blazingmq)
- [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Idempotency Keys](https://stripe.com/docs/api/idempotent_requests)
