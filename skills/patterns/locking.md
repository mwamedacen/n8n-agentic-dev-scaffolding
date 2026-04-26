---
name: pattern-locking
description: Distributed locking pattern using lock_acquisition / lock_release sub-workflows.
---

# Pattern: locking

A workflow that mutates a shared resource (a Sharepoint Excel file, a database row, an external CMS, …) needs a mutex to prevent two concurrent runs from clobbering each other. The harness provides three primitive workflows that compose into a distributed-lock pattern.

## Primitives

- **`lock_acquisition`** — Execute Workflow Trigger; takes `scope` input and acquires a lock on it. Replace the placeholder Set node with a real Redis SETNX (or equivalent) call before deploying to prod.
- **`lock_release`** — Execute Workflow Trigger; releases the lock on the same `scope`.
- **`error_handler_lock_cleanup`** — Error Trigger; releases held locks if the protected workflow errored before reaching `lock_release`.

## How to wire it in

1. `create-lock.md` (one-time) — copies the three primitives into your workspace. Ships with a placeholder Set "Acquired" / "Released" body; replace with real Redis lock semantics in your workspace before prod.
2. `add-lock-to-workflow.md` — wraps an existing workflow in lock acquire / release Execute Workflow nodes around its main body.

## Scope expression

Each invocation passes a `scope` field to the lock workflows. The default expression is `={{ $execution.id }}` — fine for "one execution at a time" semantics. For per-resource locking (e.g., one Excel file at a time), use something like `={{ 'excel-' + $json.fileId }}`.

## Caveats

- The placeholder Set nodes in the lock primitives DO NOT acquire a real lock. They just acknowledge the call. You must replace the body of `lock_acquisition` and `lock_release` with real Redis (or other backing-store) calls before relying on locking semantics.
- See `skills/integrations/redis/lock-pattern.md` for the canonical Redis SETNX recipe (when added in a later phase).
