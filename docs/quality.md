# Offline quality and review boundaries

From the starter checkout, install its declared dependencies in a local `.venv`
and the report scripts directory as described in [tool setup](tools.md).
This contributor gate also requires Git and a Git checkout for branch metadata
review. The private family's intake/capture/report commands do not require Git.

```powershell
.\.venv\Scripts\python.exe tools\quality_gate.py
```

The gate checks required dependencies, source syntax, project instruction/skill
links, candidate-file restrictions, and Python/Node synthetic regressions.
It verifies Python pins, Node manifest/lock parity and installed locked package
versions. Declared Python suites must exist and collect tests; skipped or empty
suites fail. The Node suite must execute its named cases with a nonzero passing
count and no skipped/cancelled/todo cases.
It does not install packages, access a network, invoke a model or open a browser.
Missing prerequisites and incomplete checks fail explicitly.

Tests generate new media/records and private project folders in temporary
directories. The onboarding rehearsal exercises the copied project-local
commands: intake, GEDCOM/story/eulogy evidence, capture, catalogue, round,
correction, source-span metadata, a completed scoped negative distinct from a
blocked task, and checked paired reports. It also checks existing-canon mode and
that originals/existing-store sentinels do not change.

The starter checkout's fictional public example is exercised from a newly
initialised temporary project. Its checked-in HTML is checked against the same
draft and captures as a freshly generated DOCX, so a stale or altered preview
fails the gate. Licence and dependency-notice preservation is checked in both
canonical-store modes.

Failure tests cover existing destinations/outputs, unsafe paths, corrupt inputs,
undefined or swapped citations/media/captions, exact spans, source changes,
print-DPI boundaries and delivery/rollback faults. Fault tests assert that the
injected failure actually occurred and use resolved temporary paths.

Targeted development commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_capture.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_reports.py
```

CI declares Python 3.12/Node 24 on Windows and Linux, with public dependency
installation and read-only repository permissions. A configured CI workflow is
not evidence it has run; inspect actual results before making platform claims.
Tests are not included in a private family's initializer payload.

## What the gate cannot prove

Structural correctness is not historical truth, legal publication rights,
consent, privacy completeness or attractive Word pagination. File checks cannot
recognise every possible personal detail. Review every candidate file manually,
including defaults, comments, templates, error paths and generated synthetic
output. Independently review relevant branch metadata before any commit/push.

The generic candidate check has no private family-name list or dependency on
another project. Sensitive review lists remain outside the repository.
Synthetic test markers do not replace a full manual/content/history review.

All local tools assume one cooperative writer per project. Integrity checks,
exclusive creation, staging and rollback do not replace backups or filesystem
permissions. Unsupported source formats are explicitly preserved without a
claim that they were decoded, transcribed or visually verified.
