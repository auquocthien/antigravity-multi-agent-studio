---
name: concurrency-safe-engine
description: >-
  Use this skill when implementing QThread workers, mutex locks, non-blocking asynchronous pipelines,
  Antigravity CLI subprocess streaming, and clean process lifecycle termination.
---

# Concurrency-Safe Engine Skill

## Overview
Guidelines for building robust background worker threads and asynchronous communication architectures in Linux desktop applications.

## Key Procedures
1. **Thread Separation**:
   - Long-running tasks, subprocess pipes, or model calls must run inside dedicated `QThread` instances.
   - Never call `time.sleep()` on the Qt main GUI thread.

2. **Signals & Slots**:
   - Pass immutable data models or structured packets (`StandardMessagePacket`) via `pyqtSignal`.
   - Connect signals to UI slots with thread-safe queuing.

3. **Subprocess Streaming**:
   - Stream stdout/stderr chunks asynchronously line-by-line.
   - Cleanly terminate child processes with `terminate()` followed by `kill()` on timeout upon SIGINT/SIGTERM.
