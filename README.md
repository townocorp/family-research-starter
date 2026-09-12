# Family research starter

**Family history needs evidence, not a more confident guess.**

An **early-stage, evidence-led family research starter for GitHub Copilot and
Claude Code**, with included research and report skills. Create a private family
folder, collect what you already have, record evidence and uncertainty, work
through bounded research rounds, and produce checked DOCX and self-contained
HTML reports.

I'm Mike Townsend. I developed the process and skills over six months across five
private family research projects. This repository is the reusable, early-stage
version of that work, not the families' records or findings. That experience is
the background to the workflow, not a claim that this software is mature or that
an AI can establish historical truth. A tidy report can still be wrong (mine
included). Keep the sources and the unanswered questions.

**Keep real research outside this checkout.** This shareable starter contains
tools, generic templates and synthetic tests, not a family's records. The
initializer creates no Git repository, remote, account, upload or subscription.
The starter's code, documentation, skills and fictional examples are available
under the [MIT licence](LICENSE): free to use, adapt and redistribute, including
commercially, while retaining the required notice. It comes without warranty.
That licence does not grant rights to anyone's family or archive material.

## See an example

[Read the fictional P001/P002 case](docs/example/README.md): a remembered move in
1912, a register entry from 1911, and a report that leaves the move date unresolved
rather than choosing the tidier story. All people, places, documents and events
are invented, not anonymised family research or a public figure's biography.
The example includes a generated HTML preview and steps to reproduce both the
Word and HTML reports locally.

## Quick start

Prerequisites: Python 3.12 and Node.js 24 with npm. The local tools do not need an
AI account; optional Copilot/Claude use requires the appropriate account, client
and consent to its data processing. See [tool setup](docs/tools.md).

From this starter checkout, choose an owner identifier and create a **new**
private folder. The destination's parent must already exist.

```powershell
python tools\starter.py init ..\private-family --owner P001 --canon markdown --skills
```

Already maintain an authoritative workbook or genealogy application? Keep it:

```powershell
python tools\starter.py init ..\private-family --owner P001 --canon existing --canon-location "<your chosen canonical store>" --skills
```

The existing store is recorded, not opened or migrated. `project.json` is
configuration, **not a new facts database**. An existing destination is always
refused, even if empty. There is no force/merge mode.

Enter the new folder and install its local dependencies explicitly:

```powershell
Set-Location ..\private-family
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix tools\report\scripts --ignore-scripts --no-audit --no-fund
```

On Linux, use `python3`, forward-slash paths and `.venv/bin/python`; no activation
or global settings change is needed. The initializer has copied the declared
runtime, guides and optional skills, not installed packages or Git history.

1. Complete `research/intake.md`: owner, scope, privacy boundaries, canonical
   store and permitted services. Record remembered people/dates as attributed
   starting claims, not established facts.
2. Put existing artefacts in `originals`: certificates, scans, photos, GEDCOM
   exports, stories, interviews and **eulogies**. Record who supplied them, when,
   their context and consent. Keep raw recordings and text separate from
   transcripts, OCR, translations and interpretations in `derived`.
3. Copy `evidence/capture-template.json` to a new metadata file and replace every
   `REPLACE_` field. Choose a stable evidence ID such as `E001`.
4. Capture a deliberately selected local file, then check the inventory:

```powershell
.\.venv\Scripts\python.exe tools\starter.py capture --project . --file originals\eulogies\E001.txt --metadata evidence\capture-E001.json
.\.venv\Scripts\python.exe tools\starter.py check --project .
```

Capture preserves source bytes, creates a provenance sidecar and updates a
separate generated catalogue. It does not change your canonical facts.

Copy the round template, agree a bounded question, research permitted sources,
capture as you go, and close the round with findings, leads, negatives, blockers
and corrections. See the [complete research process](docs/research-process.md).

Prepare a report from `reports/drafts/report-template.md`, replacing its
placeholders and binding citations to captured evidence:

```powershell
.\.venv\Scripts\python.exe tools\starter.py report --project . --draft reports\drafts\round-001.md --output reports\releases\round-001
```

The command checks both formats before delivery. Existing outputs are refused;
use a new round name, or explicitly `--overwrite` after review. Add
`--print --min-dpi 300` for a strict effective-DPI check. Local delivery is **not**
permission to publish. See [report syntax and limits](docs/reports.md).

## Included skills

`--skills` installs the same two canonical directories into the private folder's
`.claude/skills`: **family-research** and **family-report**. This project location
is supported by Copilot CLI, Copilot in VS Code and Claude Code. Each skill links
to the same guides and local commands. There is no global installation.

Open the private folder in your chosen client and invoke `/family-research` or
`/family-report`. [Official discovery instructions](docs/tools.md#skill-discovery)
explain client differences. Claude web Projects support deliberately uploaded
knowledge and analysis, not automatic installation of this local runtime.

## Scope and quality

Included: safe intake, local evidence/provenance, manual research-round ledgers,
two reusable skills, and checked paired reports. Not included: archive/API
adapters, purchases, browser/auth helpers, automated OCR/transcription, vector
search, GEDCOM import/merge, hosted publication or PDF report rendering.

From the starter checkout, after its own local dependency setup, run:

```powershell
.\.venv\Scripts\python.exe tools\quality_gate.py
```

This offline gate creates synthetic records/media in temporary directories and
rehearses a new family's installed commands. It never visits real family folders
or live browsers. See [quality boundaries](docs/quality.md),
[privacy and sharing](docs/privacy-and-sharing.md) and
[dependency notices](THIRD_PARTY_NOTICES.md).
