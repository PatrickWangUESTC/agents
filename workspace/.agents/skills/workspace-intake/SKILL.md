---
name: workspace-intake
description: Define inputs, deliverables, and observable acceptance criteria when a workspace task has ambiguous requirements or mixed source files.
---

Inspect only the supplied input paths and relevant project instructions. Establish
what the user wants to receive and which inputs are authoritative. Separate hard
requirements from your implementation choices. If a critical input is absent,
identify it precisely while continuing work that does not depend on it.

For multi-step tasks, write `artifacts/task-contract.md` with the goal, input paths,
output paths, constraints, and observable checks. Avoid a contract document for a
trivial edit. Do not turn the contract into an extra approval gate.

When requirements conflict, prefer the user's current explicit instruction.
Describe an unresolved ambiguity rather than silently changing the task.
