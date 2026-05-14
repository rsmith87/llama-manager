# llama.cpp Frontend Feature Roadmap (Power Users + App Developers)

## Goal
Prioritize frontend features that unlock advanced llama.cpp controls for power users and reproducible workflows for app developers, while fitting the current architecture:
- UI: `llama_manager/ui/index.html`, `llama_manager/ui/app.js`, `llama_manager/ui/styles.css`
- API edge: `llama_manager/api/routes_chat.py`
- Chat routing/proxy: `llama_manager/core/chat_proxy.py`
- Provider startup config: `llama_manager/providers/llama_cpp.py`

## Current Baseline
Current chat request fields are limited to:
- `messages`
- `temperature`
- `max_tokens`
- `reasoning`
- `target`

Streaming exists with SSE fallback to non-streaming responses. The UI already has chat send/stop/regenerate flows and route metadata chips.

## Phase 1: Power Controls + Repro (Highest ROI)

### 1.1 Expand Per-request Sampling Controls

#### Backend
Extend `ChatRequestBody` in `llama_manager/api/routes_chat.py` with typed optional fields and validation:
- `top_p`
- `top_k`
- `min_p`
- `repeat_penalty`
- `seed`
- `stop` (string or list form normalized)
- `n_predict` alias handling for `max_tokens`

Keep strict validation at API edge (ranges/defaults), then pass normalized payload into existing proxy path.

#### Frontend
Add advanced controls in chat UI (`index.html` + `app.js`):
- Input controls for all supported sampling fields
- Preset selector (Balanced / Deterministic / Creative)
- “Diff from defaults” display for quick debugging

### 1.2 Repro Bundle Export/Import

#### Frontend-first
Add “Copy Repro JSON” per assistant response in transcript rendering:
- Model name
- Route target and resolved route
- Sampling parameters
- Prompt history for that run
- Timestamp

Store presets locally first (`localStorage`) to avoid introducing persistence complexity too early.

#### Optional API follow-up
If team wants shared presets later, add `/chat/presets` endpoints in a later slice.

### 1.3 Streaming Telemetry

Parse available timing/token info from stream chunks in `readChatStream` path:
- First-token latency
- Tokens/sec
- Total generation latency

Display telemetry beside route chips in transcript.

## Phase 2: Structured Output + Template Debugging

### 2.1 Structured Output Panel

#### Frontend
Add advanced section:
- JSON Schema input
- Grammar input
- Mutual-exclusion toggle (schema OR grammar)
- Client-side schema validation before send

#### Backend
Extend `ChatRequestBody` with:
- `json_schema`
- `grammar`

Return clear validation errors for incompatible combinations.

### 2.2 Prompt/Template Inspector

Add rendered prompt preview and token estimate before send.

Implementation option:
- Add helper endpoint in `routes_chat.py` / proxy to return rendered prompt + estimate.

UI should keep this in an Advanced accordion.

### 2.3 Capability Introspection

Add endpoint:
- `GET /chat/capabilities/{model}`

Response includes supported knobs/features (streaming, grammar, schema, embeddings availability, etc.).

UI consumes capabilities and disables unsupported controls instead of failing at request time.

## Phase 3: Session State + Batch Tooling

### 3.1 Session Save/Restore

Add chat proxy endpoints for session snapshot metadata and restore hooks.

UI adds:
- Save session
- Load session

Primary use cases:
- Deterministic continuation
- Debug/repro across runs

### 3.2 Batch Inference Runner

Add a new UI tab for prompt suites and parameter variants.

Inputs:
- Prompt set
- Parameter matrix / named variants

Outputs:
- Timing table
- Token counts
- Output preview cells

### 3.3 Embeddings Workbench (Capability-gated)

If runtime supports embeddings endpoints:
- Batch embed UI
- Vector metadata display
- Export JSON/CSV

Fallback:
- If unsupported, expose that status through capabilities and disable this page.

## Cross-Cutting Contracts

### API Edge Discipline
`routes_chat.py` remains the canonical validation and normalization layer.

### Runtime Separation
Keep llama-server process startup flags in `providers/llama_cpp.py`.
Do not move per-request generation controls into process-level configuration.

### Testing
Add/extend tests in:
- `tests/test_api.py` for field validation + normalization
- Streaming/fallback behavior tests for chat route behavior where feasible

## Implementation Sequence
1. Phase 1.1 + 1.2 together (sampling controls + repro bundle)
2. Phase 2.1 next (structured output panel)
3. Phase 2.3 (capabilities endpoint)
4. Phase 1.3 (telemetry) if stream payload supports required timing signals, otherwise after proxy enrichment
5. Phase 3 features after earlier contracts stabilize

## First Execution Slice (Starting Now)
Implement a PR-sized slice:
- Expand `ChatRequestBody` and payload plumbing for advanced sampling fields
- Add chat advanced controls in UI
- Add repro JSON export for each assistant response
- Add/update tests for request validation and payload handling

This slice is designed to be independently shippable and unlock immediate value for both power users and app developers.
