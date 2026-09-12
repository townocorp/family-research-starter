# Dependency notices

The starter's code, documentation, skills and fictional examples use the
[MIT licence](LICENSE), approved by the owner on 2026-09-12. This file records
third-party dependency terms; it does not relicense those dependencies or grant
rights to family/archive material.

No dependency implementation, virtual environment or `node_modules` directory
is vendored or copied by the initializer. Explicit package installation retains
the upstream notices with each installed distribution. Retain those notices if
redistributing dependencies; this summary does not replace their full terms.

Metadata and the direct installed licence files were reviewed on 2026-09-12.
Versions are recorded in `requirements.txt` and the report `package-lock.json`.
All resolved npm tarball hosts in that lock are `registry.npmjs.org`.

| Direct dependency | Version | Declared terms | Authoritative notice |
| --- | --- | --- | --- |
| Pillow | 12.3.0 | MIT-CMU, not plain MIT | [Pillow licence](https://github.com/python-pillow/Pillow/blob/main/LICENSE); the installed wheel's `pillow-12.3.0.dist-info/licenses/LICENSE` also contains bundled component notices |
| pypdf | 6.14.2 | BSD-3-Clause | [pypdf licence](https://github.com/py-pdf/pypdf/blob/main/LICENSE); installed `pypdf-6.14.2.dist-info/licenses/LICENSE` |
| docx | 9.7.1 | MIT | [docx licence](https://github.com/dolanmiu/docx/blob/master/LICENSE); installed package `LICENSE` |
| image-size | 2.0.2 | MIT | [image-size licence](https://github.com/image-size/image-size/blob/main/LICENSE); installed package `LICENSE` |

The installed Pillow wheel includes notices for its bundled native components.
Its top-level MIT-CMU expression is not a blanket relicensing of all those
components. We do not copy that wheel or its native libraries into this repo.

## Locked Node dependency tree

These are the declarations of the resolved packages, not a licence grant by this
project. Keep each package's actual notices and upstream conditions.

| Dependency | Version | Declared terms |
| --- | --- | --- |
| @types/node | 25.9.6 | MIT |
| core-util-is | 1.0.3 | MIT |
| hash.js | 1.1.7 | MIT |
| immediate | 3.0.6 | MIT |
| inherits | 2.0.4 | ISC |
| isarray | 1.0.0 | MIT |
| jszip | 3.10.2 | MIT OR GPL-3.0-or-later; the MIT alternative is the intended permissive option, not both terms combined |
| lie | 3.3.0 | MIT |
| minimalistic-assert | 1.0.1 | ISC |
| nanoid | 5.1.16 | MIT |
| pako | 1.0.11 | MIT AND Zlib; preserve both sets of conditions |
| process-nextick-args | 2.0.1 | MIT |
| readable-stream | 2.3.8 | MIT |
| safe-buffer | 5.1.2 | MIT |
| sax | 1.6.1 | BlueOak-1.0.0 |
| setimmediate | 1.0.5 | MIT |
| string_decoder | 1.1.1 | MIT |
| undici-types | 7.24.6 | MIT |
| util-deprecate | 1.0.2 | MIT |
| xml | 1.0.1 | MIT |
| xml-js | 1.6.11 | MIT |

Python and Node.js are separately installed runtimes with their own licences.
The test harness uses Python's standard library and Node's built-in test runner.
No third-party test fixtures, document images or family manuscripts are included.

Acquired photographs, records, audio, transcripts and living-person information
have separate copyright, custody, privacy and consent requirements. The
software licence does not authorise their publication.
