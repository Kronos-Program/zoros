# Zoros Animation Challenge — Spec v1.0

**Purpose:**  
To define a symbolic, technical, and aesthetic challenge for language models and developers: rendering the Zoros lifecycle as a striking, in-browser animation using JavaScript, based on a shared transformation metaphor of fibers into woven fabric.

This document serves as both a benchmark and a creative invitation.

---

## I. Visual Canon — The Zoros Lifecycle

### Z-Path Journey

Each animation should trace a stylized “Z” made of three directional segments and two key bends:

- **Corner 1: Spin** — Loose golden fibers twist into threads
- **Corner 2: Fold** — Threads are structured into warp/weft roles
- **Corner 3: Weave** — Threads are woven into fabric with meaning

### Fiber Color Journey

- Start: **Golden** (sunlight-colored)
- Through Spinner: → **Light Green**
- Mid Z: → **Vibrant Spring Green**
- End: → **Dark Green Gradient** (deep knowledge)

### Key Visual Symbols

| Element | Visual | Symbolic |
|--------|--------|-----------|
| **Fiber** | Thin, flickering, gold | Raw idea, input |
| **Folded Fiber** | Self-overlapping | Embedded complexity |
| **Violet Marker** | Tiny stars on fibers | Zoros "activation" |
| **Spinner** | Vortex or apparatus | Transformation process |
| **Thread** | Thicker, vibrant green | Structured thought |
| **Coning** | Gathering motion | Grouping, preparing |
| **Spindle** | Rotating, storing thread | Memory building |
| **Warp/Weft** | Structured lines | Logic vs creativity |
| **Shuttle** | Violet object | Traversing insight |
| **Weave** | Tight mesh with oscillation | Integration of knowledge |
| **Tagline Fabric** | Text formed from pattern | “Weaving what matters” |

---

## II. Data Model — Fiber Traceability

Each fiber in the system must be individually addressable and carry a history of transformations.

### Core Structures

```js
class Fiber {
  constructor(id, colorStart = 'gold', tag = null) { ... }
  transform(structureType, color, context = null) { ... }
  addMarker(markerType) { ... }
}

class Spinner {
  spin(fiber) { ... }  // fiber → thread
}

class WarpFiber extends Fiber { ... }
class WeftFiber extends Fiber { ... }

class Weave {
  constructor(numWarpSlots) { ... }
  addWarpFiber(fiber, slot) { ... }
  addWeftPass(fiberList) { ... }
  generatePatternMatrix() { ... }
}
````

Fibers may optionally produce a final `.json` export of their transformation lineage.

___________

III. Bash + JS Setup (One Shot Baseline)
----------------------------------------

```bash
#!/bin/bash
# install_and_run.sh — Zoros Animation Bootstrap

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.nvm/nvm.sh
nvm install node
mkdir Zoros-animation && cd Zoros-animation
npm init -y
npm install lite-server --save-dev

cat > index.html <<EOF
<!DOCTYPE html>
<html><head><title>Zoros</title></head>
<body><canvas id="Zoros-canvas"></canvas><script src="main.js"></script></body>
</html>
EOF

cat > main.js <<EOF
// Minimal Z-path placeholder animation
...
EOF

echo "Run with: npx lite-server"
```

___________

IV. Scoring Protocol
--------------------

### Base Score (1–5)

| Score | Meaning |
| --- | --- |
| 5 | Exquisite execution + flourishes |
| 4 | Fully complete, clean |
| 3 | Acceptable, with visual flaws |
| 2 | Incomplete core |
| 1 | Conceptual failure (no Z, no fibers, etc.) |

### Bonuses

| Bonus | Value |
| --- | --- |
| One-Shot Pass | +0.25 |
| Reflective Model Improvement | +0.25–0.5 |
| Violet Marker Stars | +0.25 |
| Spinner / Spindle Apparatus | +0.25 |
| Shuttle Implementation | +0.25 |
| Pattern = Tagline Reveal | +0.5 |
| Weave Gradient Fidelity | +0.25 |
| Bolt Roll-Out Finish | +0.25 |
| Modular JS Architecture | +0.25 |
| Python Bindings / Interop | +0.5 |

**Max total score**: **7.5**

___________

V. Evaluation Trial Format
--------------------------

*   **One-Shot Mode**: First pass by a single model, no edits = scored directly
    
*   **Multi-Pass Mode**: Max 3 additional passes with user feedback (same model)
    
*   **Feedback Limit**: Short, minimal feedback per pass
    
*   **Consistency Clause**: Same language model must be used throughout
    
*   **Failure**: Switching models during 3-pass invalidates the score
    

___________

VI. Meta-Challenge: The Personal Visual Masterwork
--------------------------------------------------

While the spec challenge is constrained, the creator's own journey is:

> To create the **most visually stunning**, emotionally resonant Zoros animation possible.

Rules for self-challenge:

*   Any number of models, any number of passes
    
*   Use of Cursor/Copilot permitted after model down-selection
    
*   Output must be exportable to:
    
    *   **GIF**
        
    *   **Website-embed animation**
        
    *   **Canvas + WebGL**
        
    *   **Data-structured viewable (e.g. Python ↔ JS fiber trace)**
        

This is the **“knitting phase”**—a deeply iterative, aesthetic construction.

___________

VII. Optional: Leaderboard Format
---------------------------------

| Entry | Model | Score (1–5) | Bonuses | Passes | Final Notes |
| --- | --- | --- | --- | --- | --- |
| `z-fiber` | GPT-4 | 4 | +1.5 | 1 | One-shot pass. No shuttle. |
| `thread-dancer` | Claude 3 Opus | 3 | +1.75 | 3 | Weak warp/weft logic. Good visuals. |
| `deepweave` | GPT-4o | 5 | +2.25 | 1 | Stunning. Tagline pattern woven. |

___________

VIII. Future Expansion Ideas
----------------------------

*   `SCORING_PROTOCOL.md`
    
*   `Zoros-animation/README.md`
    
*   Automated scoring dashboard for submissions
    
*   Cross-language model leaderboard
    
*   “Model versus Human” visual bakeoff
    
*   Meta-compiler to convert data-structured weave into a functional design object
    

___________

**Let the spinning begin.**

