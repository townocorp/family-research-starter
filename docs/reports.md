# Checked DOCX and HTML reports

Write the draft inside the selected private project. The report command stages
an inert JSON intermediate, renders DOCX and self-contained HTML from the same
data, checks them, and then delivers a local pair under `reports/releases`.

```powershell
.\.venv\Scripts\python.exe tools\starter.py report --project . --draft reports\drafts\round-001.md --output reports\releases\round-001
```

Use the same command with `--print --min-dpi 300` for print media. A digital
report can report low-DPI warnings; print mode fails below the chosen effective
DPI in either axis. Upscaling does not create source detail. Figures fit
proportionally inside 528 by 720 CSS pixels (5.5 by 7.5 inches). The controlled
A4 layout has one-inch margins and reserves two inches for caption/source text.
Long captions and final pagination still require visual review.

## Authoring subset

Start with `reports/drafts/report-template.md` and replace every `REPLACE_`
marker. Required frontmatter is `title`, `author`, `date` and integer `round`.
Dates may be ISO, a year or `unknown`. Metadata is explicit, never inferred from
names, account settings or prose.

Supported narrative: `#` chapter headings, `##`/`###` subheadings, paragraphs,
`**bold**`, `*italic*`, simple `-` bullets, numeric citations and attributed
one-line quotes. Quotes use `> text | speaker/source and context attribution`.
Keep uncertainty, contradictory evidence, corrections and outstanding questions
in normal sections.

Every citation uses `[^N]`, with a positive numeric ID and a definition:

```text
[^1]: E001 | precise page/line/time locator | full source and custody/public URL citation
```

The evidence must have been captured. Repeated and nonconsecutive IDs are
supported. Undefined, duplicate and unused references fail. A local capture
supports verification, not a guarantee of historical truth.

Figures use:

```text
![E001|Caption with citation [^1]|Source attribution](../../evidence/captures/E001/source.png)
```

The path is relative to the Markdown draft and must remain inside the private
project. The figure must be the original bytes in its declared capture and must
cite that evidence. Make crops/rotations/other derivatives as separate captures
with their own provenance. Initially only upright PNG/JPEG images are embedded;
EXIF-rotated images require an explicitly prepared upright derivative. Keep the
unaltered original.

This is not a general Markdown renderer: tables, nested/ordered lists, fenced
code, raw HTML blocks and other unsupported block structures are rejected.
Use prose/bullets instead. Do not pass CommonJS/JavaScript modules as report data.
The intermediate JSON is derived report input, **not** the canonical facts store.

## Delivery and checks

The pipeline checks nonempty content, complete ordered content blocks, citation occurrence
order and numbering, reference backlinks, image hashes, decode completeness,
figure-caption-source association, both-axis page fit and optional print DPI.
Extra narrative, unsupported hiding attributes and altered template styles fail;
required text appearing somewhere in the output is not sufficient.
It detects missing/corrupt captures and sources changed during generation.
Self-contained HTML embeds image bytes and uses system fonts: no remote assets,
telemetry or absolute machine image paths are needed.

Existing output names are refused, including a repeat run. Prefer a new round
name. `--overwrite` explicitly allows replacing that local pair only; a staging
or checking failure preserves the previous pair. Single-writer delivery uses
complete staged files; it is not an operating-system transaction across two
files. A delivery failure attempts rollback and reports incomplete rollback with
retained recovery files. Do not delete recovery files until the owner reviews
them. A stale release lock also requires inspection; do not automatically break
another writer's lock.

DOCX container timestamps/identifiers may vary across builds. The invariant is
checked content and evidence fidelity, not identical ZIP bytes. A print-DPI pass
does not certify visual layout, pagination, accessibility or historical accuracy.

Direct developer tools, if needed, also require explicit `--project`:
`markdown_to_data.py` writes only JSON with exclusive output creation;
`create_docx.js` and `create_html.js` accept only `.json` and never overwrite
existing files; `check_report.py` checks a supplied local pair. Prefer the
top-level `report` command for normal use, since it provides paired delivery.

Before distribution, review both outputs visually, living-person privacy,
attribution, sensitive inferences, reproduction rights, consent and audience.
Local generation is not publication approval.
