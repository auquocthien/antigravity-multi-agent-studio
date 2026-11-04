---
name: playwright-automation
description: >-
  Use this skill when executing browser-based end-to-end tests, headless automation,
  UI component visual validation, API mock intercepting, and web app validation using Playwright.
---

# Playwright Test Automation Skill

## Overview
Guidelines and operational standards for automated browser testing, cross-browser validation (Chromium, Firefox, WebKit), and end-to-end regression suites using Playwright.

## Capabilities & Runbooks
1. **Headless Execution**:
   - Run tests headlessly in CI/CD and desktop environments:
     ```bash
     npx playwright test --reporter=line
     ```
2. **Visual & UI Snapshot Testing**:
   - Capture element and full-page screenshots to detect unintended CSS/layout regressions.
3. **Network Interception & Mocking**:
   - Mock API responses and monitor HTTP payload payloads to ensure robust offline behavior.
4. **Tracing & Error Diagnostics**:
   - Enable Playwright trace recording on failure to diagnose broken selector chains or timeout exceptions.
