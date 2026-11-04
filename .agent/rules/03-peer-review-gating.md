# Peer Review Gating Protocol

## Review & Gating Rules
1. **Bidirectional Review**:
   - Dev 1 (UI) and Dev 2 (Core) must exchange `PEER_REVIEW_REQUEST` packets prior to escalating code to QA.
   - Code changes crossing boundaries must be mutually inspected for thread safety and layout compatibility.

2. **Gating Criteria**:
   - Reviewer must verify that:
     - No direct blocking calls exist on the GUI thread.
     - All mutex acquisitions are guarded against deadlocks.
     - Accessible color contrasts meet WCAG AAA standards.
   - Only when satisfied, the Reviewer issues an `APPROVAL_NOTICE`.
