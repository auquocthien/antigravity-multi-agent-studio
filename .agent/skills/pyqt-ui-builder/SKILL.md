---
name: pyqt-ui-builder
description: >-
  Use this skill when designing, implementing, styling, or refactoring PyQt6/PySide6 desktop UI
  components, layout structures, custom vector canvas painters, and Slate Dark / OLED tokens.
---

# PyQt UI Builder Skill

## Overview
This skill provides runbook procedures and design tokens for building high-performance Linux desktop interfaces with PyQt6.

## Guidelines
1. **Design Tokens**:
   - Backgrounds: Primary Canvas `#0B0F19`, Elevated Surface `#111827`, Card Border `#1F2937`.
   - Text: Primary `#F9FAFB`, Secondary `#9CA3AF`, Muted `#6B7280`.
   - Accents: Sky Blue `#38BDF8`, Emerald `#10B981`, Amber `#F59E0B`, Rose `#EF4444`.

2. **Vector Rendering**:
   - Use `QPainter` with `RenderHint.Antialiasing`.
   - Avoid hardcoded text arrows; use geometric vector paths (`drawLine`, `drawPath`) for smooth HiDPI rendering.

3. **Accessibility**:
   - Pair status indicators with text labels and shape variations (LED dots, tooltips).
