# ⚡ Antigravity Multi-Agent Studio

> **Autonomous Multi-Department Real-Time Orchestration Platform for Linux Desktop**  
> Powered by PyQt6, Antigravity CLI Bridge, Employee Persona Profiles (`.md`), and Workspace/Global Customization Engine (`.agent/`).

---

## 🌟 Key Highlights

### 1. 🏢 Multi-Department Modular Squads
The studio enables seamless dynamic switching between distinct organizational departments without restarting or breaking pipeline topology:
- 💻 **Software Engineering Squad**:
  - 👑 **Alexander Vance** (`Leader / Architect`) — Requirements partitioning & dynamic reasoning budget escalation.
  - 💻 **Elena Rostova** (`Dev 1: UI & Layout`) — Responsive PyQt6 visual layout & status design.
  - 💻 **Marcus Chen** (`Dev 2: Core & Threads`) — Concurrency-safe worker threads, bus logging & agy CLI bridging.
  - 🛡️ **Dr. Sarah Jenkins** (`Code Reviewer`) — Boundary auditing, race condition prevention & strict gating.
  - 🧪 **David Kim** (`Runtime Tester`) — Headless QA, Playwright E2E browser automation & Chrome DevTools MCP diagnostics.
- 🎬 **Video & Media Production Squad**:
  - 🎬 **Liam Parker** (`Creative Director`) — Video storyboards, scene decomposition & pacing architecture.
  - 🎨 **Chloe Bennett** (`Motion Graphics Dev`) — Remotion React compositions, spring physics & kinetic typography.
  - 🎙️ **Julian Ross** (`Audio & Captions Eng`) — Voiceover narration cues, audio ducking & kinetic SRT sync.
  - 🔍 **Maya Lin** (`Video Quality Reviewer`) — Frame rate audits, WCAG subtitle contrast & color grading.
  - 🚀 **Ethan Cole** (`Remotion Render QA`) — Headless `npx remotion render` compilation & MP4 validation.

### 2. 👤 Employee Persona System (`personas/*.md`)
Every agent acts as a true professional employee with a dedicated Markdown profile defining:
- Real name, years of experience (8–15+ yrs), and domain specialties.
- Operating mindset, boundary constraints, and communication standards.
- Custom in-app live editor and file browser in Tab 3 to tailor persona prompts on the fly.

### 3. 🧩 Antigravity Customization Architecture (`.agent/` & Global)
- Automatically discovers workspace rules (`01-architecture-boundaries.md`, `02-investigate-before-fix.md`, `03-peer-review-gating.md`) and global rules.
- Integrates workspace & global skills (`headless-qa-automation`, `playwright-automation`, `concurrency-safe-engine`, `chrome-devtools`, `pyqt-ui-builder`, `remotion-create`, etc.).
- Configures workspace MCP servers (`.agent/mcp.json`) for Chrome DevTools and Playwright automation.
- Agents autonomously reference and invoke designated skills, MCP tools, and rule boundaries in their reasoning traces.

### 4. 🎨 UI/UX Pro Max Architecture
- **Tab 1: Pipeline Flow (Horizontal)** — Left-to-right vector line connectors (fork, parallel, peer-review gating, join, straight line) with smooth glassmorphism cards.
- **Tab 2: Agent Details (Live Inspector)** — Multi-agent roster selection with high-performance real-time syntax-colored activity streams.
- **Tab 3: Settings & Configuration** — Matrix to adjust live Antigravity models, reasoning budgets (Low/Medium/High/Max), and assign employee persona files.

---

## 🚀 Quick Start

### Prerequisites
- Linux OS (x86_64)
- Python 3.10+
- `libxcb` and standard Linux desktop display libraries

### Running from Source
```bash
git clone https://github.com/auquocthien/antigravity-multi-agent-studio.git
cd antigravity-multi-agent-studio

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Launch application
python3 src/main.py
```

### Running Unit Test Suite
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m unittest tests/test_concurrency.py
```

### Building Standalone Linux Binary (PyInstaller)
```bash
bash build_linux.sh
# Output executable generated at: dist/linux-utility
```

---

## 📁 Repository Structure

```
antigravity-multi-agent-studio/
├── .agent/                    # Workspace-level Rules, Skills & MCP
│   ├── rules/                 # Boundary & gating guidelines
│   ├── skills/                # Domain-specific automation skills (playwright, pyqt, concurrency)
│   └── mcp.json               # MCP server configuration (Chrome DevTools & Playwright)
├── assets/                    # Application icons & visual resources
├── personas/                  # 10 Professional Employee Persona Markdown Profiles
│   ├── 01_leader_architect.md
│   ├── 02_dev_frontend.md
│   ├── 03_dev_backend.md
│   ├── 04_code_reviewer.md
│   ├── 05_qa_tester.md
│   ├── 06_creative_director.md
│   ├── 07_motion_graphics_dev.md
│   ├── 08_audio_captions_dev.md
│   ├── 09_video_quality_reviewer.md
│   └── 10_render_qa_engineer.md
├── src/
│   ├── core/
│   │   └── engine.py          # Multi-department concurrency engine & packet bus
│   ├── ui/
│   │   ├── main_window.py     # 3-tab layout, department switcher, inspector
│   │   └── tree_node.py       # Compact vector node cards
│   └── main.py                # Desktop entrypoint
├── tests/
│   └── test_concurrency.py    # 8 headless unit tests
├── build_linux.sh             # Standalone ELF packaging script
├── requirements.txt           # Python dependencies (PyQt6, etc.)
└── README.md
```

---

## 📜 License
MIT License. Crafted with Antigravity AI Pair Programming.
