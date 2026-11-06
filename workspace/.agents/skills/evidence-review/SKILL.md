---
name: evidence-review
description: Check a deliverable against explicit acceptance criteria and write an evidence-linked result report, including failed or unverified checks.
---

Read the task prompt or `artifacts/task-contract.md` and inspect the actual output.
Choose checks that can falsify a claimed result. Reuse existing tests when they
cover the relevant behavior; a syntax check alone does not establish functionality.

For each material criterion record pass, fail, or unverified, plus the command,
artifact location, or observation that supports that status. Retain negative
results. State the scope of a partial check without generalizing it to the whole
system. If a check would require unavailable tools or access, mark it unverified.

Put a concise result in `artifacts/report.md` when a report is useful. Include
output paths and remaining issues. Do not label the result accepted merely
because a process returned zero or the expected file exists.
