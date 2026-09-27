# Architecture maps

Two maps of this codebase, written as [archify](https://github.com/tt-a1i/archify)
specifications. The JSON files are the source of truth; the HTML is generated from them.

| Spec | What it shows |
|---|---|
| `deepresearch.architecture.json` | The three clients, the Python engine's modules, the shared `contract/`, and the outside services - every component carries `sources` pinned to a commit |
| `deepresearch-pipeline.workflow.json` | One research run of the Python engine: the main path, the rescue pass, and every early exit |

## How they were checked (2026-09-27)

- **Mechanically:** `archify validate --quality showcase` passes both (9 artifact checks,
  0 errors, 0 warnings). For the architecture map, `--repo-root` verified all 22 source
  references against the files at the pinned revision (`822e95e`, v1.18.2).
- **In a browser:** `archify visual-check` passes both at 1440x900, 1600x1000, 1920x1080
  and 2048x1320 (no overflow, node text at or above 6px).
- **By meaning:** each map was checked claim by claim against the code by a reviewer
  that had not written it. Tracing the maps that way found four engine defects, fixed in
  v1.18.2, and several wrong claims in the first drafts - the model seam drawn in the
  wrong module, two of the contract's three readers missing, an exit edge missing.

A map is a claim about the code. When the code moves, re-pin `meta.repository.revision`
and re-run the commands below; a cited line that no longer exists fails validation.

## Rebuild

```bash
A=~/.zcode/skills/archify/bin/archify.mjs      # or wherever archify is installed
node $A deliver architecture docs/architecture/deepresearch.architecture.json \
  docs/architecture/deepresearch.architecture.html --quality showcase --repo-root .
node $A deliver workflow docs/architecture/deepresearch-pipeline.workflow.json \
  docs/architecture/deepresearch-pipeline.workflow.html --quality showcase
node $A visual-check docs/architecture/deepresearch.architecture.html
node $A visual-check docs/architecture/deepresearch-pipeline.workflow.html
```

The HTML, screenshots and visual-check sidecars are generated, so git ignores them.
