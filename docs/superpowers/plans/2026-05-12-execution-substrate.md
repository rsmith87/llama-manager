# Llama Manager Execution Substrate Plan

## Summary

Build `llama_manager` into a distributed execution substrate without making it an autonomous planner. The controller owns the durable queue, job state, leases, events, cancellation state, and artifacts. Agents own execution by optionally running a background worker that claims controller jobs and reports progress/results.

The first typed execution contract is intentionally narrow: `llm.generate`. It reuses the existing chat request behavior and proves the controller-owned queue plus agent-owned execution loop end to end.

## V1 Implementation

- Add typed validation for `llm.generate` jobs while keeping generic jobs backward compatible.
- Add an opt-in agent worker that claims jobs from the controller and executes `llm.generate` locally.
- Add cooperative cancellation for assigned/running jobs and immediate cancellation for queued jobs.
- Add durable event polling plus SSE replay/live streaming for job events.
- Extend capability and claim metadata enough for an outside planner to make basic placement decisions.

## Future Typed Contracts

The current mode split points to a controller-owned queue with agent-owned execution. That is the right boundary, but `llm.generate` should not be the final task contract.

Future work should add more typed contracts only after `llm.generate` is stable in real use. Candidate contracts include:

- `llm.embed` for embeddings.
- `llm.rerank` if supported by configured local models.
- `model.convert` for HF-to-GGUF conversion.
- `model.quantize` for quantization jobs.
- `artifact.transform` for file-oriented post-processing.
- Tool or workflow execution contracts, if a separate planner/runtime needs them.

Each new contract should define a stable payload schema, result schema, retry/cancel behavior, capability requirements, and worker ownership. Planning, task decomposition, recursive delegation, and policy decisions should remain outside `llama_manager` unless a later design explicitly changes that boundary.

## Verification

- Focused tests should cover typed validation, worker claim/execute/complete/fail behavior, cancellation, SSE event replay, and existing generic job compatibility.
- Full backend verification should use `uv run pytest -v`.
