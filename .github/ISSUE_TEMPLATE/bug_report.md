---
name: Bug report
about: Something behaved wrongly
labels: bug
---

**What happened, and what you expected instead.**

**The run log.** Attach the `--out` JSON, or the `.log` beside it. `stats.searchHealth`
and `stats.agentErrors` usually identify the problem in one line — a run with every
general-web backend at `results: 0` saw a scholarly-only slice of the web, and its coverage
gaps are a search artifact rather than a bug.

**Reproduce:**
```
python3 -m deepresearch --question "..." --depth quick --out bug.json
```

**Environment:** OS, `python3 --version`, and whether you used `ANTHROPIC_API_KEY` or a
local Claude Code credential.
