# God-File Review (Round 2): Abstraction and Maintainability

Date: 2026-05-12
Status: Open findings to work through

## Prioritized Findings

### P1. `ChatProxy` is still a god-object with mixed responsibilities

- File: `llama_manager/core/chat_proxy.py`
- Current scope includes:
  - request payload shaping
  - target resolution (local vs node)
  - remote model probing
  - request and stream transport calling
  - KV slot capability probing
  - model capability introspection
- Risk:
  - high coupling across chat, embeddings, stream, and KV behavior
  - difficult to test in focused units
  - one change can unintentionally affect multiple call paths
- Refactor direction:
  - extract `TargetResolver` concern (`_resolve_*`, `_is_model_running_on_node`)
  - extract `RequestBuilder` concern (`_build_request`, `_build_slots_request`)
  - extract `CapabilityInspector` concern (`capabilities`, KV probes)

### P1. Chat route exception mapping is duplicated

- File: `llama_manager/api/routes_chat.py`
- Repeated handling patterns across:
  - `POST /chat/{model_name}`
  - `POST /chat/{model_name}/stream`
  - `POST /chat/{model_name}/embeddings`
- Risk:
  - drift in status code/detail shape
  - repetitive route logic reduces readability
- Refactor direction:
  - introduce shared mapping utility (for `KeyError`, `ModelNotRunningError`, `httpx.HTTPStatusError`, `httpx.HTTPError`)
  - keep endpoint-specific behavior minimal and explicit

### P2. `OrchestrationRepo` remains broad across lifecycle + reporting concerns

- File: `llama_manager/core/orchestration_repo.py`
- Current class includes:
  - lifecycle write commands (`create/claim/progress/complete/fail/sweep`)
  - retention/archive/report methods (`prune`, `list_terminal_jobs_before`, `list_artifacts`, counts)
- Risk:
  - class growth makes review and ownership boundaries less clear
- Refactor direction:
  - split internal responsibilities into lifecycle vs retention/reporting units
  - keep public interface stable during split

### P2. Runtime `TypeError` fallback for injected request callables can mask bugs

- File: `llama_manager/core/chat_proxy.py`
- Affected methods:
  - `_call_request`
  - `_call_stream_request`
- Risk:
  - `TypeError` from real runtime bugs can be treated as adapter mismatch fallback
- Refactor direction:
  - normalize callable signatures when injected (adapter/wrapper in constructor)
  - remove runtime exception-based signature probing

## Suggested Execution Order

1. P1: Deduplicate chat route exception mapping (low risk, high readability gain)
2. P1: Decompose `ChatProxy` by concern behind stable facade
3. P2: Split `OrchestrationRepo` internal responsibilities
4. P2: Replace `TypeError` fallback with explicit callable adapters

## Acceptance Criteria Per Item

- No endpoint contract changes unless explicitly intended
- Existing tests remain green
- Add focused regression tests where control-flow is refactored
- Keep behavior-preserving changes isolated by concern

## Tracking Checklist

- [x] Item 1 complete: chat route exception mapping deduplicated
- [x] Item 2 complete: `ChatProxy` concern split implemented
- [x] Item 3 complete: `OrchestrationRepo` concern split implemented
- [x] Item 4 complete: callable signature fallback removed via adapter
