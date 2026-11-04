---
name: headless-qa-automation
description: >-
  Use this skill when executing automated headless GUI tests with QT_QPA_PLATFORM=offscreen,
  testing signal propagation, fuzzing event storms, and verifying standalone PyInstaller ELF binaries.
---

# Headless QA Automation Skill

## Overview
Standards and execution runbooks for validating PyQt6 applications without requiring a physical X11/Wayland display server.

## Verification Procedures
1. **Headless Execution Command**:
   ```bash
   QT_QPA_PLATFORM=offscreen /mnt/data/linux-desktop-utility/.venv/bin/python3 -m unittest tests/test_concurrency.py
   ```
2. **Process Events Polling**:
   - In unit tests, pump events with `app.processEvents()` to allow cross-thread signal delivery.
3. **Packaging Integrity Smoke Test**:
   - Run `timeout 3s dist/linux-utility` under `QT_QPA_PLATFORM=offscreen`. Exit code 124 confirms the event loop ran without crashing.
