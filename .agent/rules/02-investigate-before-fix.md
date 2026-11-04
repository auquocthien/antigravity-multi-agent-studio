# Investigate Root Cause Before Modifying Code

## Core Principles
Before making any source code modifications or configuration changes:

1. **Investigate Root Cause First**:
   - Read and analyze relevant source code, error logs, stack traces, and reproduction steps.
   - Never speculate or rush to patch code without identifying the underlying root cause.

2. **Display & Explain Detailed Rationale**:
   - Before executing file modifications, the agent must formulate:
     - **Error Summary**: Observed symptoms and specific error descriptions.
     - **Root Cause Analysis**: Technical explanation of why the failure occurred.
     - **Affected Scope**: Specific files, classes, and line numbers.
     - **Proposed Fix Strategy**: Rationale and technical approach.

3. **Execute & Verify**:
   - Implement the change cleanly.
   - Run automated headless test verification to confirm fix without regression.
