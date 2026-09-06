"""M7 hardening deterministic test package.

Covers the three M6-discovered production gaps repaired in M7:
- A. Framed catalog integrity
- B. C++ witness journal append-only history (compile-verified)
- C. Execution/submission deadline enforcement

No live UE 5.6 Scenarios 1-8. No workflow/action-runner tests.
"""