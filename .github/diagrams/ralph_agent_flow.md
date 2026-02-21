# Ralph Agent — Flow Diagrams

## Scope

Ralph is an autonomous GitHub issue resolver. It is triggered by a single label (`ralph-autofix`) and operates entirely within CI — no human intervention required from trigger to PR.

**What Ralph does:**

- Reads a GitHub issue and creates a dedicated branch
- Drives a Cline CLI coding agent in a TDD loop: write code, run tests, escalate model on failure
- For frontend issues: starts the dev server, captures before/after screenshots, and runs a visual QA pass via a vision-capable Cline instance
- Commits all changes and opens a PR with a cost report and screenshot diff
- Runs a self-review phase in fresh context: a read-only reviewer Cline inspects the diff and issues a verdict; on rejection, a fixer Cline applies corrections and the cycle repeats

**What Ralph does not do:**

- Does not handle issues without the `ralph-autofix` label
- Does not push directly to `main` — all changes land in a PR for human merge
- Does not retry indefinitely — coding attempts, review iterations, and self-heal attempts are all capped by config
- Does not require any human input once the label is applied

**Boundaries and constraints:**

| Dimension | Limit |
|---|---|
| Total CI timeout | 90 minutes |
| Coding attempts | `max_coding_attempts` (from `agent_config.yml`) |
| Review iterations | `max_review_iterations` |
| Self-heal attempts per fix | `max_heal_attempts` |
| Models | All via OpenRouter (DeepSeek, MiniMax, Qwen VL) — not Anthropic direct |
| Secrets exposure | `.cline-*` dirs scrubbed before any upload step, even on failure |

---



## Phase 1: `ralph_agent.py` — Main Coding Agent

```mermaid
flowchart TD
    A([Start]) --> B[Parse issue env vars\nValidate OPENROUTER_API_KEY]
    B --> C[Create git branch\nralph/issue-N-slug]
    C --> D[Post start comment\non GitHub issue]
    D --> E{Issue has\n'hard' label?}
    E -- Yes --> F[Configure hard_cline\nfor all attempts]
    E -- No --> G[Configure default_cline\nwith hard_cline fallback]
    F & G --> H{Frontend issue?}
    H -- Yes --> I[Start dev server\nInit vision_cline with MCP]
    H -- No --> J[Skip server & vision]

    I & J --> K

    subgraph CODING_LOOP["TDD Coding Loop (max N attempts)"]
        K{Attempt 1?} -- Yes --> L[Load tdd_prompt.md\nwith issue details]
        K -- No --> M[Run tests]
        M --> N{Tests pass?}
        N -- Yes --> O([Break — tests passed])
        N -- No --> P[Load escalate_prompt.md\nwith diff + test output]
        L & P --> Q{Hard issue or\nfinal attempt?}
        Q -- Yes --> R[Run hard_cline]
        Q -- No --> S[Run default_cline]
        R & S --> T{ClineError?}
        T -- Yes --> U[Log warning, continue]
        T -- No --> K
        U --> K
    end

    O & T --> V[Run final test check]
    V --> W{Tests passed?}
    W -- Yes --> X[Log success]
    W -- No --> Y[Log warning\nProceed anyway]

    X & Y --> Z{Frontend issue\n& server running?}
    Z -- Yes --> AA[Restart server\nRun vision_cline\nCapture after screenshots]
    Z -- No --> AB[Skip screenshots]
    AA & AB --> AC[Stop server]

    AC --> AD[Commit & push\nfix: issue title]
    AD --> AE{GitError?}
    AE -- Yes --> AF[Post failure comment\non issue]
    AF --> AG([Raise RuntimeError / exit 1])
    AE -- No --> AH[Calculate OpenRouter cost\nBuild PR body with screenshots]
    AH --> AI[Create PR via gh CLI]
    AI --> AJ[Write PR_NUMBER, PR_URL,\nBRANCH to GITHUB_OUTPUT]
    AJ --> AK[Post completion comment\non issue]
    AK --> AL([Done])
```

---

## Phase 2: `self_review.py` — Self-Review Loop

```mermaid
flowchart TD
    A([Start]) --> B[Parse issue, PR_NUMBER, BRANCH\nValidate OPENROUTER_API_KEY]
    B --> C

    subgraph REVIEW_LOOP["Review Loop (max N iterations)"]
        C[Spin up fresh reviewer Cline\ncline-reviewer-i, read-only] --> D[Get diff vs main\nGet changed files]
        D --> E{Diff empty?}
        E -- Yes --> F[Label PR: review-passed\nPost: No changes, auto-approve]
        F --> G([Return])
        E -- No --> H[Truncate diff if > 30k chars]
        H --> I[Load review_prompt.md\nwith issue + diff]
        I --> J{Frontend issue?}
        J -- Yes --> K[Read visual verdict file\nInject visual QA into prompt]
        J -- No --> L[Skip visual QA]
        K & L --> M[Run reviewer Cline]
        M --> N{ClineError?}
        N -- Yes --> O[Log error\nAuto-approve: LGTM\nLabel PR: review-passed]
        O --> G
        N -- No --> P[Parse verdict from output]
        P --> Q{Verdict?}
        Q -- LGTM --> R[Label PR: review-passed\nPost review summary]
        R --> G
        Q -- NEEDS CHANGES --> S{Last iteration?}
        S -- Yes --> T([Exit loop])
        S -- No --> U[Spin up fixer Cline\ncline-fixer-i]
        U --> V[Load review_fix_prompt.md\nwith reviewer feedback]
        V --> W[Run fixer Cline]
        W --> X

        subgraph HEAL_LOOP["Self-Heal Loop (max M attempts)"]
            X[Run tests] --> Y{Tests pass?}
            Y -- Yes --> Z([Return true])
            Y -- No --> AA{More heal\nattempts?}
            AA -- Yes --> AB[Load heal_prompt.md\nRun fixer Cline]
            AB --> X
            AA -- No --> AC([Return false])
        end

        Z & AC --> AD[Commit & push fixes\nfix: address review feedback round i]
        AD --> AE{GitError?}
        AE -- Yes --> AF[Log error\nBreak — stale diff risk]
        AF --> T
        AE -- No --> C
    end

    T --> AG[Label PR: review-needs-attention\nPost final review summary]
    AG --> AH([Done])
```

---

## CI/CD Workflow: `ralph-autofix.yml`

```mermaid
flowchart TD
    A([Issue labeled\n'ralph-autofix'\nOR workflow_dispatch]) --> B{Label is\n'ralph-autofix'\nor manual trigger?}
    B -- No --> C([Skip — do nothing])
    B -- Yes --> D[Concurrency lock\nralph-autofix-ISSUE_N\nnon-cancelling]

    D --> E[Checkout main\nfetch-depth: 0]
    E --> F[Setup Node 22\n+ npm cache]
    F --> G[Setup Python 3.12\n+ pip cache]
    G --> H[npm ci\nInstall project deps]
    H --> I[pip install -r requirements.txt]
    I --> J[npm install -g cline@latest]
    J --> K[npm install -g @playwright/mcp\nnpx playwright install chromium]

    K --> L{OPENROUTER_API_KEY\nset?}
    L -- No --> M[::error:: secret not set]
    M --> FAIL
    L -- Yes --> N[curl openrouter.ai/api/v1/key]
    N --> O{HTTP 200?}
    O -- No --> P[::error:: key rejected]
    P --> FAIL
    O -- Yes --> Q[Syntax-check all .py files\npython -m py_compile]
    Q --> R[Run agent unit tests\npytest .github/scripts/tests/]
    R --> S{Tests pass?}
    S -- No --> FAIL
    S -- Yes --> T[Run ralph_agent.py\nstep id: agent]
    T --> U[Remove .cline-agent*\n.cline-vision* dirs\nalways runs]
    U --> V[Upload screenshots artifact\nif-no-files-found: ignore\nalways runs]
    V --> W{agent step\noutcome == success?}
    W -- No --> FAIL
    W -- Yes --> X[Run self_review.py\nwith PR_NUMBER + BRANCH\nfrom agent outputs]
    X --> Y([Workflow complete])

    FAIL([failure]) --> Z[Post failure comment\non GitHub issue\nwith workflow run link]
    Z --> ZZ([Exit 1])
```

---

## End-to-End: Trigger → Fix → Review

```mermaid
flowchart LR
    subgraph TRIGGER["GitHub Event"]
        A([Issue labeled\nralph-autofix])
    end

    subgraph CI["ralph-autofix.yml (ubuntu-latest, 90 min)"]
        B[Environment Setup\nNode 22 · Python 3.12\nCline · Playwright]
        C[Validate API Key\nSyntax check + pytest]

        subgraph AGENT["ralph_agent.py"]
            D[Parse issue\nCreate branch]
            E{Frontend?}
            E -- Yes --> F[Start server\nInit vision Cline]
            E -- No --> G[Skip server]
            F & G --> H

            subgraph TDD["TDD Loop"]
                H[Attempt N\ntdd_prompt / escalate_prompt] --> I{Tests pass?}
                I -- No, retry --> H
                I -- Yes --> J([Break])
            end

            J --> K{Frontend?}
            K -- Yes --> L[After screenshots\nVisual review]
            K -- No --> M[Skip]
            L & M --> N[Commit & push\nCreate PR]
        end

        O[Scrub .cline dirs\nUpload screenshots]

        subgraph REVIEW["self_review.py"]
            P[Fresh reviewer Cline\nRead-only context]
            Q{Verdict?}
            Q -- LGTM --> R[Label: review-passed]
            Q -- NEEDS CHANGES --> S[Fixer Cline\n+ self-heal loop]
            S --> T[Commit fixes\nRe-review]
            T --> P
            T -- Max iterations --> U[Label: review-needs-attention]
        end
    end

    A --> B --> C --> D
    N --> O --> P
    R & U --> V([Done])
```
