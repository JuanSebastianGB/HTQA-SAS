# HTQA Event Microservice - Flow Diagram

## Architecture Overview (Clean/Hexagonal)

```mermaid
graph TB
    subgraph External["🌐 External"]
        Client["Client / IoT Device"]
    end

    subgraph Presentation["🎭 PRESENTATION LAYER"]
        AM["AuditMiddleware<br/>Request/Response logging"]
        Auth["get_api_key<br/>X-API-Key validation"]
        Router["POST /events<br/>Route Handler<br/>(rate limit en handler)"]
        Health["GET /health<br/>Health Check"]
    end

    subgraph Application["⚙️ APPLICATION LAYER"]
        ES["EventService<br/>Orchestrator"]
        IS["IdempotencyService<br/>SETNX 5-min window"]
        RLS["RateLimiterService<br/>fixed-window counter (Redis)"]
        SC["SeverityClassifier<br/>métricas → *_down/offline →<br/>keywords → metadata.priority → default"]
        NS["NotificationService<br/>Email alerts"]
    end

    subgraph Domain["🏛️ DOMAIN LAYER"]
        Event["Event Entity<br/>dataclass"]
        Severity["Severity Value Object<br/>LOW/MEDIUM/HIGH/CRITICAL"]
        Status["EventStatus Value Object<br/>PENDING/PROCESSED/FAILED"]
        Ports["Repository Ports<br/>EventRepository, CacheRepository"]
    end

    subgraph Infrastructure["🔧 INFRASTRUCTURE LAYER"]
        Repo["SQLAlchemyEventRepository<br/>PostgreSQL Async"]
        Cache["RedisCacheRepository<br/>Redis Async"]
        Notifier["MockEmailNotifier<br/>Email simulation"]
        DB[(PostgreSQL<br/>events, audit_logs)]
        Redis[(Redis<br/>rate limits, idempotency)]
    end

    Client -->|"1. HTTP POST /events<br/>X-API-Key: xxx"| AM
    AM -->|"2. Capture metadata<br/>method, path, IP"| Auth
    Auth -->|"3. Validate API key"| Router
    Router -->|"4. EventCreateDTO"| ES

    ES -->|"5. check_rate_limit"| RLS
    RLS --> Redis
    ES -->|"6. check_idempotency<br/>source + device_id + event_type"| IS
    IS --> Redis
    ES -->|"7. classify<br/>event_type + metric_value + metadata"| SC
    SC -->|"Severity enum"| Event

    ES -->|"8. Create Event<br/>status: PENDING"| Event
    Event -->|"9. Persist"| Repo
    Repo --> DB

    ES -->|"10. mark_completed"| IS
    IS --> Redis

    ES -->|"11. Si CRITICAL: schedule"| BT["Background Task<br/>_process_critical_event"]
    ES -->|"12. Return 202 Accepted<br/>EventResponseDTO (no espera BG)"| Return["HTTP 202 al cliente"]

    BT -->|"13. Fetch event"| Repo
    Repo --> DB
    BT -->|"14. Send notification"| NS
    NS -->|"15. Email (MockEmailNotifier)"| BT
    BT -->|"16. Update status<br/>PROCESSED or FAILED"| Repo
    Repo --> DB

    Return -->|"17. 202 + X-Process-Time"| AM
    AM -->|"18. Save audit record"| DB
    AM -->|"19. Response"| Client

    classDef external fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef presentation fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef application fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef domain fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef infrastructure fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef db fill:#fff9c4,stroke:#f57f17,stroke-width:2px,stroke-dasharray: 5 5

    class Client external
    class AM,Auth,Router,Health presentation
    class ES,IS,RLS,SC,NS application
    class Event,Severity,Status,Ports domain
    class Repo,Cache,Notifier infrastructure
    class DB,Redis db
```

El cliente recibe `202 Accepted` en el paso 12; las tareas 13–16 del background pueden seguir en paralelo y no bloquean la respuesta HTTP.

## Request Flow Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Client as 🌐 Client
    participant Audit as Audit<br/>Middleware
    participant Auth as API Key<br/>Validation
    participant Route as POST /events<br/>Route
    participant ES as Event<br/>Service
    participant Redis as 🔴 Redis
    participant SC as Severity<br/>Classifier
    participant Repo as Event<br/>Repository
    participant DB as 🗄️ PostgreSQL
    participant BG as Background<br/>Task

    Client->>Audit: POST /events {device_id, event_type, metric_value, metadata, ...}
    Note over Client,Audit: Headers: X-API-Key, Content-Type: application/json

    Audit->>Audit: Capture: method, path, IP, timestamp
    Audit->>Auth: Forward request

    Auth->>Auth: Validate X-API-Key against settings
    Auth-->>Route: api_key (valid)

    Route->>ES: check_rate_limit(api_key)
    ES->>Redis: fixed-window counter (INCR + EXPIRE)
    Redis-->>ES: allowed=true

    Route->>ES: check_idempotency(source, device_id, event_type)
    ES->>Redis: SETNX idempotency:{source}:{device_id}:{event_type} "pending" EX 300
    Redis-->>ES: was_set=true (not duplicate)

    Route->>ES: create_event(EventCreateDTO, background_tasks)

    ES->>SC: classify(event_type, metric_value, metadata)
    Note over ES,SC: Reglas: métricas → *_down/offline → keywords → metadata.priority
    SC-->>ES: Severity (p. ej. CRITICAL si device_down o metric ≥ 100)

    ES->>ES: Create Event entity (status: PENDING)
    ES->>Repo: create(event)
    Repo->>DB: INSERT INTO events
    DB-->>Repo: event_id = UUID
    Repo-->>ES: Event (persisted)

    ES->>Redis: SET idempotency:{source}:{device_id}:{event_type} event_id EX 300

    alt Severity == CRITICAL
        ES->>BG: add_task(_process_critical_event, event_id)
    end

    ES-->>Route: EventResponseDTO (202 Accepted)
    Route-->>Audit: Response

    Audit->>DB: INSERT INTO audit_logs (async)
    Audit-->>Client: 202 Accepted + X-Process-Time

    Note over BG: Runs asynchronously
    BG->>Repo: get_by_id(event_id)
    Repo->>DB: SELECT FROM events
    DB-->>Repo: Event
    Repo-->>BG: Event

    BG->>BG: Notify via email (MockEmailNotifier)
    BG->>Repo: update(event, status=PROCESSED)
    Repo->>DB: UPDATE events SET status='processed'
```

## Critical Events Background Processing

```mermaid
graph LR
    subgraph Trigger["🔥 Trigger"]
        CE["severity == CRITICAL<br/>(métricas, *_down/offline, …)"]
    end

    subgraph Processing["⚡ Background Processing"]
        Fetch["Fetch event from DB"]
        Verify["Verify still CRITICAL"]
        Notify["Send email notification<br/>(NOTIFICATION_RECIPIENT_EMAIL)"]
        Update["Update status"]
    end

    subgraph Outcomes["📊 Outcomes"]
        Success["✅ PROCESSED"]
        Failure["❌ FAILED<br/>log error"]
    end

    CE --> Fetch
    Fetch --> Verify
    Verify -->|"Yes"| Notify
    Notify -->|"Success"| Update
    Update -->|"OK"| Success
    Notify -->|"Exception"| Update
    Update -->|"Error"| Failure

    classDef trigger fill:#ffccbc,stroke:#bf360c,stroke-width:2px
    classDef processing fill:#bbdefb,stroke:#0d47a1,stroke-width:2px
    classDef outcomes fill:#c8e6c9,stroke:#1b5e20,stroke-width:2px
    classDef failure fill:#ffcdd2,stroke:#b71c1c,stroke-width:2px

    class CE trigger
    class Fetch,Verify,Notify,Update processing
    class Success outcomes
    class Failure failure
```

## Middleware Chain (Outer → Inner)

```mermaid
graph LR
    subgraph Chain["Middleware (main.py: solo AuditMiddleware; rate limit en ruta)"]
        A["🌐 Incoming Request"] --> B["1️⃣ AuditMiddleware<br/>• Capture method, path, IP<br/>• Sanitize sensitive headers<br/>• Calculate process time<br/>• Excludes: /health, /docs"]
        B -->|"✅ Forwarded"| C["2️⃣ FastAPI Router<br/>• Auth: X-API-Key<br/>• POST /events: rate limit e idempotencia Redis,<br/>SeverityClassifier, persistencia"]
        C -->|"Response"| D["← AuditMiddleware<br/>• Save audit record to DB<br/>• Add X-Process-Time header"]
        D --> E["🌐 Response to Client"]
    end

    classDef middleware fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef external fill:#f5f5f5,stroke:#616161,stroke-width:2px

    class B,C,D middleware
    class A,E external
```

## Data Flow: Event Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: POST /events<br/>(Rate limit ✓, Idempotency ✓)
    PENDING --> PROCESSED: Background task completes<br/>(Critical events only)
    PENDING --> FAILED: Background task exception<br/>(Critical events only)
    PENDING --> [*]: Non-critical events<br/>(remain PENDING, no background task)
    PROCESSED --> [*]
    FAILED --> [*]

    note right of PENDING
        Event persisted in PostgreSQL
        Idempotency key in Redis (5 min)
        Request counted in fixed window (rate limit)
    end note

    note right of PROCESSED
        Email notification sent
        Status updated in PostgreSQL
        Idempotency key still valid (5 min)
    end note

    note right of FAILED
        Error logged
        Status updated to FAILED
        No retry mechanism (current)
    end note
```

## Infrastructure Dependencies

```mermaid
graph TB
    subgraph App["HTQA Event Microservice"]
        Main["main.py<br/>FastAPI App"]
    end

    subgraph Services["External Services"]
        PG[(PostgreSQL<br/>htqa_events)]
        RD[(Redis<br/>Cache & Rate Limiting)]
    end

    Main -->|"asyncpg"| PG
    Main -->|"redis.asyncio"| RD

    subgraph DB_Tables["PostgreSQL Tables"]
        Events["events<br/>• id, source, customer_id<br/>• device_id, event_type<br/>• occurred_at, metric_value<br/>• metadata (JSON)<br/>• severity, status<br/>• created_at<br/>Indexes: severity+occurred_at,<br/>source+device_id+event_type,<br/>customer_id+created_at"]
        AuditLogs["audit_logs<br/>• id, timestamp<br/>• api_key (sanitized)<br/>• method, path<br/>• status_code, ip_address<br/>• created_at"]
    end

    subgraph Redis_Keys["Redis Keys"]
        RateLimit["rate_limit:{api_key}<br/>INCR + EXPIRE (ventana fija)"]
        Idempotency["idempotency:{source}:{device_id}:{event_type}<br/>Value: event_id or 'pending'<br/>TTL: 300 seconds"]
    end

    PG --> Events
    PG --> AuditLogs
    RD --> RateLimit
    RD --> Idempotency
```
