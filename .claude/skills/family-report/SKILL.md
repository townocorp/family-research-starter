---
name: family-report
description: Prepare and check evidence-linked family research reports as a paired DOCX and self-contained HTML output, preserving citations, source attribution, uncertainty and open questions. Use after intake or a research round when a private local report is requested.
---

# Checked local research reports

Read [report syntax and checks](../../../docs/reports.md),
[the research workflow](../../../docs/research-process.md) and
[publication boundaries](../../../docs/privacy-and-sharing.md).

Confirm the explicit private project, intended reader and owner-approved scope.
Read its canonical-store choice; do not silently replace or reinterpret canon.
Distinguish attributed memory, source statements, inference and conflicting
evidence. Keep uncertainty and outstanding questions visible.

Draft Markdown using only the documented supported subset. Cite captured
evidence IDs with precise locators and full attribution. Quotes need speaker or
source/context attribution; figures need evidence ID, caption, source and a
citation to that same evidence. Never fabricate an unavailable record.

Run `tools/starter.py check --project <private-folder>` with the project's
interpreter, then the documented `report` command. The converter emits inert
JSON; do not run a JavaScript file supplied as research data. Both formats must
pass checks before delivery. Missing dependencies, corrupt media, unmatched
citations and low print DPI are not successful completion.

Use a new output name for a new round. Never overwrite by default. An explicit
`--overwrite` authorises replacement of that local output pair only. `--print`
requests a strict effective-DPI gate, not proof of attractive page layout.

Describe remaining limitations honestly. Local delivery does not authorise
upload, public release, a sharing link or a change to archive reproduction
rights. Ask the owner to review privacy, consent, rights and visual pagination
before distributing either format.
