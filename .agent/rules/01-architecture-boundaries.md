# Architecture Boundaries & Separation of Concerns

## Scope & Module Boundaries
1. **Frontend / UI Components (`src/ui/*`)**:
   - Solely owned by `agent_dev_ui` (Elena Rostova).
   - Responsible for PyQt6 layouts, widget hierarchies, QSS styling tokens, and accessible status indicators.
   - Must never directly manipulate backend threads, socket descriptors, or execute direct blocking CLI calls.

2. **Core / Systems Engine (`src/core/*`)**:
   - Solely owned by `agent_dev_core` (Marcus Chen).
   - Responsible for QThread workers, mutex locks, telemetry logging, and Antigravity CLI subprocess pipelines.
   - Must never instantiate or manipulate GUI widgets directly; all UI communication must strictly travel via Qt Signals.

3. **Code Review & Quality Gate (`agent_reviewer`)**:
   - Audits all diffs against concurrency safety, naming conventions, and boundary leaks.

4. **Runtime QA Verification (`agent_tester`)**:
   - Executes automated headless test suites against all cross-module interactions.
