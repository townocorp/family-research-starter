# Tool choice and project-local setup

Use tools for their capabilities, not a presumed model ranking. An assistant
can organise files, draft scoped queries, compare transcriptions and propose
claims. Source evidence and the owner remain responsible for the conclusions.

| Tool | Suitable work | Important boundary |
| --- | --- | --- |
| Local Python/Node tools included here | Intake, hashes, provenance, catalogue and paired reports | No network, archive search, OCR or AI inference in these commands |
| Copilot CLI or Copilot agent mode in VS Code | Authorised file/terminal workflow with the included skills | Client permissions, account/organisation policies and cloud processing still apply |
| Claude Code | Authorised project files/terminal commands and the same skills | Local command execution is not local-only model processing |
| Claude web Projects | Deliberately uploaded knowledge, focused chats and analysis | Uploads are data transfers; this is not installation of these terminal tools or a browser-login bridge |
| Archive website or public API chosen by the owner | Finding/downloading permitted records | No adapter, premium access or credential handling is provided here |
| Separately selected OCR/transcription/translation tool | Attributed derivatives of selected originals | Check privacy, consent and errors; retain raw input and method/version |

## Prerequisites

The supported local runtime baseline is **Python 3.12 and Node.js 24 with npm**.
No AI account is needed for the deterministic local tools. Install Python/Node
using their official distributions; do not let the initializer install software.
Obtain the starter checkout through your normal Git/download process.

The initializer itself uses Python's standard library. After creating a private
folder, install dependencies inside that folder, not globally:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci --prefix tools\report\scripts --ignore-scripts --no-audit --no-fund
```

Linux equivalents:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci --prefix tools/report/scripts --ignore-scripts --no-audit --no-fund
```

These package-install commands access public package registries; the local
capture/report/quality commands themselves make no network requests. Packages
are not copied from another environment. Missing dependencies fail explicitly.

Use that `.venv` interpreter to run `tools/starter.py`; it propagates its
interpreter to the Node renderer's local image preflight. No persistent
environment change is necessary. Node renderers can use `FAMILY_RESEARCH_PYTHON`
for an explicitly selected interpreter when invoked directly.

For AI clients, use current official installation/login instructions yourself:
[Copilot CLI quick start](https://docs.github.com/en/copilot/get-started/cli-quickstart)
and [Claude Code setup](https://code.claude.com/docs/en/setup). Start `copilot` or
`claude` in the private folder after reviewing trust and data boundaries.
The starter never installs a client globally or changes a user profile.

## Skill discovery

Official support checked **2026-09-12**. Installed versions, entitlements and
organisation restrictions may differ; check the linked docs if discovery fails.

The repository and optional initializer payload contain:

```text
.claude/skills/family-research/SKILL.md
.claude/skills/family-report/SKILL.md
```

One canonical placement works for all three supported local clients:

- **Copilot CLI:** [official skill instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
  explicitly support project `.claude/skills`. Start a session, or use
  `/skills reload`, then `/skills list` or `/skills info family-research`.
  Invoke `/family-research` or `/family-report`.
- **Copilot in VS Code:** [official Agent Skills documentation](https://code.visualstudio.com/docs/agent-customization/agent-skills)
  explicitly supports `.claude/skills`. Open the private folder in VS Code and
  use `/skills` in Copilot Chat to inspect/configure workspace skills. This UI
  is not the CLI's `/skills reload` command.
- **Claude Code:** [official skills documentation](https://code.claude.com/docs/en/skills)
  specifies project `.claude/skills/<skill-name>/SKILL.md`. Start `claude` in
  the private folder; invoke `/family-research` or `/family-report`.

Each skill uses matching lower-kebab-case name/folder, standard description
metadata and relative guide links. No broad shell pre-approval or dynamic
command injection is included. Project instructions refer to one workflow:
`AGENTS.md`, the small `CLAUDE.md` import and `.github/copilot-instructions.md`.
See [Copilot CLI custom instructions](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions)
and [Claude Code memory/instruction files](https://code.claude.com/docs/en/memory).
Instructions guide an assistant; they are not enforced access controls.

**Claude web Projects are different.** [The official description](https://support.claude.com/en/articles/9517075-what-are-projects)
describes uploaded knowledge and project instructions. Uploading these Markdown
guides can provide context, but does not run the CLI, install project-local
skills or give access to a signed-in browser. Choose every upload explicitly.

## Browser and provider boundaries

Leave paid-archive login and MFA to the owner. Prefer permitted original
downloads; capture screenshot limitations honestly. Never export cookies,
passwords or connection tokens; change profiles, make profile junctions, kill
a browser/process, or claim an automatic Python-to-extension bridge.

No browser integration is shipped or installed. If an owner independently
chooses browser automation, review its permissions and
[the official Playwright MCP documentation](https://github.com/microsoft/playwright-mcp).
Browser-wide access is not automatically restricted to the page being researched.
Stop on access failures rather than silently switching profiles or bypassing a
restriction.

Do not assume that `.gitignore`, a private repository, a local browser, a terminal
client or content exclusion prevents cloud transfer. Consult
[Claude Code data usage](https://code.claude.com/docs/en/data-usage) and
[Copilot content-exclusion scope](https://docs.github.com/en/copilot/concepts/context/content-exclusion),
as well as your actual provider/account terms. Avoid unsupported promises about
retention, training or which product modes enforce exclusions.
