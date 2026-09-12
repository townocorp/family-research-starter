/* Shared inert-input, citation and local-media contracts for both renderers. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const { imageSize } = require('image-size');

const NOTICE = 'Private research draft. Evidence may conflict; local generation is not publication approval.';
const PAGE = Object.freeze({ width: 11906, height: 16838, margin: 1440, captionReserve: 2880 });
const IMAGE_BOX = Object.freeze({ width: 528, height: 720 });
const digest = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
function parseJson(raw) {
  const result = JSON.parse(raw);
  const tokens = raw.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g);
  let index = 0;
  function value() {
    const token = tokens[index++];
    if (token === '{') {
      const keys = new Set();
      while (tokens[index] !== '}') {
        const key = JSON.parse(tokens[index++]);
        if (keys.has(key)) throw new Error(`Duplicate JSON field: ${key}`);
        keys.add(key);
        index++;
        value();
        if (tokens[index] !== ',') break;
        index++;
      }
      index++;
    } else if (token === '[') {
      while (tokens[index] !== ']') {
        value();
        if (tokens[index] !== ',') break;
        index++;
      }
      index++;
    }
  }
  value();
  return result;
}
function text(value, name) {
  if (typeof value !== 'string' || !value.trim() || value.includes('REPLACE_')) throw new Error(`${name} must be nonempty text without template placeholders.`);
  return value;
}
function shape(value, keys, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) {
    throw new Error(`Unexpected ${name} fields.`);
  }
}
function noLinks(input) {
  const lexical = input.replace(/\\/g, '/');
  if (lexical.startsWith('//') || /^\/(?:\?\?|device|global\?\?)\//i.test(lexical) ||
      /^[A-Za-z][A-Za-z0-9+.-]+:/.test(lexical)) throw new Error('Network/device namespace paths and URIs are refused.');
  const windows = path.win32.parse(input);
  if (/^[A-Za-z]:$/.test(windows.root)) throw new Error('Drive-relative paths are refused.');
  const raw = path.isAbsolute(input) ? input : process.cwd() + path.sep + input;
  let current = path.parse(raw).root;
  for (const part of raw.slice(current.length).split(/[\\/]/)) {
    if (!part || part === '.') continue;
    current = part === '..' ? path.dirname(current) : path.join(current, part);
    try {
      const info = fs.lstatSync(current);
      if (info.isSymbolicLink() || (info.isFile() && info.nlink > 1)) throw new Error('Linked report files are refused.');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  return path.resolve(raw);
}
function within(root, input) {
  const target = noLinks(input);
  const relative = path.relative(root, target);
  if (!relative || relative.startsWith('..' + path.sep) || relative === '..' || path.isAbsolute(relative)) {
    throw new Error('Report path must stay inside its explicit private project.');
  }
  return target;
}
function local(root, relative) {
  text(relative, 'local file');
  if (path.isAbsolute(relative) || path.win32.parse(relative).root) throw new Error('Expected project-relative file.');
  return within(root, root + path.sep + relative);
}
function sameFile(a, b) {
  if (path.resolve(a) === path.resolve(b)) return true;
  if (!fs.existsSync(a) || !fs.existsSync(b)) return false;
  const x = fs.statSync(a), y = fs.statSync(b);
  return x.dev === y.dev && x.ino === y.ino;
}
function argumentsFor(argv, output = true) {
  const args = argv.slice(2), expected = output ? 4 : 3;
  if (![expected, expected + 2].includes(args.length) || args[output ? 2 : 1] !== '--project') {
    throw new Error(`Usage: node SCRIPT data.json ${output ? 'output ' : ''}--project private-folder`);
  }
  let expectedHash;
  if (args.length === expected + 2) {
    if (args[expected] !== '--input-sha256' || !/^[a-f0-9]{64}$/.test(args[expected + 1])) {
      throw new Error('Invalid frozen input hash.');
    }
    expectedHash = args[expected + 1];
  }
  const root = noLinks(args[expected - 1]);
  const dataPath = within(root, args[0]);
  if (path.extname(dataPath) !== '.json') throw new Error('Only inert .json report input is accepted.');
  const outPath = output ? within(root, args[1]) : undefined;
  if (outPath && sameFile(dataPath, outPath)) throw new Error('Output aliases its input.');
  return { root, dataPath, outPath, expectedHash };
}
function inlineTokens(value, style = {}) {
  if (value == null || value === '') return [];
  if (typeof value !== 'string') throw new Error('Narrative text must be a string.');
  const pattern = /\[\^(\d+)\]|\*\*([^*]+)\*\*|\*([^*]+)\*/g;
  const tokens = [];
  let end = 0;
  for (const match of value.matchAll(pattern)) {
    if (match.index > end) tokens.push({ text: value.slice(end, match.index), ...style });
    if (match[1] !== undefined) tokens.push({ refId: Number(match[1]) });
    else tokens.push(...inlineTokens(match[2] ?? match[3],
      { ...style, ...(match[2] !== undefined ? { bold: true } : { italic: true }) }));
    end = match.index + match[0].length;
  }
  if (end < value.length) tokens.push({ text: value.slice(end), ...style });
  return tokens;
}
const plainLabel = value => inlineTokens(value).map(t => t.refId === undefined ? t.text : String(t.refId)).join('');
function readEvidence(root, identity) {
  if (!/^E\d{3,}$/.test(identity)) throw new Error('Evidence must have a stable E ID.');
  const recordPath = local(root, `evidence/captures/${identity}/record.md`);
  const recordBytes = fs.readFileSync(recordPath), lines = recordBytes.toString('utf8').split(/\r?\n/);
  const end = lines.indexOf('---', 1), fields = {};
  if (lines[0] !== '---' || end < 1) throw new Error('Invalid evidence sidecar.');
  for (const line of lines.slice(1, end)) {
    const match = /^([a-z][a-z0-9_]*): (.+)$/.exec(line);
    if (!match || Object.hasOwn(fields, match[1])) throw new Error('Malformed evidence metadata.');
    fields[match[1]] = parseJson(match[2]);
  }
  if (fields.schema !== 1 || fields.evidence_id !== identity ||
      !/^source\.[a-z0-9]{1,11}$/.test(fields.local_artefact)) throw new Error('Evidence identity/path mismatch.');
  const file = local(root, `evidence/captures/${identity}/${fields.local_artefact}`);
  const bytes = fs.readFileSync(file);
  if (!bytes.length || fields.byte_size !== bytes.length || fields.sha256 !== digest(bytes)) {
    throw new Error(`Original bytes for ${identity} changed.`);
  }
  return { recordPath, recordHash: digest(recordBytes), file, sha256: fields.sha256 };
}
function inspectReport(data, root, dataPath, outPath) {
  const config = parseJson(fs.readFileSync(local(root, 'project.json'), 'utf8'));
  if (config.schema !== 1 || config.kind !== 'private-family-research') throw new Error('Explicit private project required.');
  shape(data, ['schema', 'meta', 'chapters', 'references'], 'report');
  shape(data.meta, ['title', 'author', 'date', 'round'], 'metadata');
  if (data.schema !== 1) throw new Error('Unknown report schema.');
  for (const key of ['title', 'author', 'date']) text(data.meta[key], key);
  if (!Number.isSafeInteger(data.meta.round) || data.meta.round < 0) throw new Error('Invalid report round.');
  if (!Array.isArray(data.chapters) || !data.chapters.length ||
      !Array.isArray(data.references) || !data.references.length) throw new Error('Narrative and evidence references are required.');
  const refs = new Map(), evidence = new Map(), assets = new Map(), occurrences = [], texts = [];
  const add = value => {
    text(value, 'narrative');
    for (const token of inlineTokens(value)) {
      if (token.refId !== undefined) {
        if (!Number.isSafeInteger(token.refId) || !refs.has(token.refId)) throw new Error(`Undefined citation ${token.refId}.`);
        occurrences.push(token.refId);
      }
    }
    texts.push(plainLabel(value));
  };
  for (const ref of data.references) {
    shape(ref, ['id', 'evidenceId', 'locator', 'short', 'long'], 'reference');
    if (!Number.isSafeInteger(ref.id) || ref.id < 1 || refs.has(ref.id)) throw new Error('Duplicate/invalid reference ID.');
    for (const key of ['evidenceId', 'locator', 'short', 'long']) text(ref[key], key);
    if (inlineTokens(ref.long).some(t => t.refId !== undefined)) throw new Error('Reference definitions cannot contain citations.');
    refs.set(ref.id, ref);
    if (!evidence.has(ref.evidenceId)) evidence.set(ref.evidenceId, readEvidence(root, ref.evidenceId));
  }
  texts.push(data.meta.title, `Prepared by ${data.meta.author}`, `Round ${data.meta.round}; ${data.meta.date}`, NOTICE);
  const chapterIds = new Set(['references']);
  let narrative = 0;
  for (const chapter of data.chapters) {
    shape(chapter, ['id', 'title', 'sections'], 'chapter');
    if (typeof chapter.id !== 'string' || !/^[a-z0-9][a-z0-9-]*$/.test(chapter.id) || chapterIds.has(chapter.id)) {
      throw new Error('Missing/duplicate/unsafe chapter ID.');
    }
    chapterIds.add(chapter.id);
    add(chapter.title);
    if (!Array.isArray(chapter.sections) || !chapter.sections.length) throw new Error('Chapter has no content.');
    for (const section of chapter.sections) {
      if (section.type === 'image') {
        shape(section, ['type', 'evidenceId', 'caption', 'source', 'file'], 'figure');
        const record = evidence.get(section.evidenceId);
        if (!record) throw new Error('Figure evidence must have a declared reference.');
        const file = local(root, section.file), buffer = fs.readFileSync(file);
        if (!sameFile(file, record.file)) throw new Error('Figure must map to its captured evidence bytes.');
        const info = imageSize(buffer);
        if (!['png', 'jpg'].includes(info.type) || !Number.isFinite(info.width) ||
            !Number.isFinite(info.height) || Math.min(info.width, info.height) <= 0) throw new Error('Report figures require PNG/JPEG.');
        if (info.orientation && info.orientation !== 1) throw new Error('Make a separately attributed upright derivative before embedding an EXIF-rotated image.');
        if (outPath && sameFile(file, outPath)) throw new Error('Output aliases a source image.');
        const scale = Math.min(1, IMAGE_BOX.width / info.width, IMAGE_BOX.height / info.height);
        if (Math.min(info.width * scale, info.height * scale) < 1) {
          throw new Error('Figure aspect ratio is too extreme for the page; prepare an attributed derivative.');
        }
        const renderedWidth = Math.round(info.width * scale);
        const image = { file, buffer, type: info.type, width: info.width, height: info.height,
          renderedWidth, renderedHeight: Math.round(info.height * scale),
          sha256: digest(buffer), evidenceId: section.evidenceId,
          caption: plainLabel(section.caption), source: plainLabel(section.source) };
        const figureCitations = [...inlineTokens(section.caption), ...inlineTokens(section.source)]
          .filter(t => t.refId !== undefined);
        if (!figureCitations.some(t => refs.get(t.refId)?.evidenceId === section.evidenceId)) {
          throw new Error('Figure caption/source must cite its own evidence.');
        }
        assets.set(section, image);
        add(section.caption); add(section.source);
      } else {
        if (!['h2', 'h3', 'p', 'quote', 'bullet'].includes(section.type)) throw new Error('Unsupported section type.');
        shape(section, section.type === 'quote' ? ['type', 'text', 'attribution'] : ['type', 'text'], 'section');
        add(section.text);
        if (section.type === 'quote') add(section.attribution);
        if (['p', 'quote', 'bullet'].includes(section.type)) narrative++;
      }
    }
  }
  if (!narrative) throw new Error('Nonempty narrative is required.');
  texts.push('References');
  for (const ref of refs.values()) {
    if (!occurrences.includes(ref.id)) throw new Error(`Reference ${ref.id} is never cited.`);
    texts.push(`${ref.id}. ${plainLabel(ref.long)}`);
  }
  if (assets.size) {
    const python = process.env.FAMILY_RESEARCH_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
    const decoded = spawnSync(python, [path.join(__dirname, 'media_preflight.py')], {
      input: JSON.stringify([...assets.values()].map(image => image.file)),
      encoding: 'utf8', windowsHide: true, timeout: 60000,
    });
    if (decoded.error || decoded.status !== 0) throw new Error(`Full image decode incomplete: ${decoded.stderr || decoded.error?.message}`);
    const checked = JSON.parse(decoded.stdout);
    if (!Array.isArray(checked) || checked.length !== assets.size) throw new Error('Incomplete image decode coverage.');
    [...assets.values()].forEach((image, i) => {
      if (checked[i].sha256 !== image.sha256 || checked[i].width !== image.width || checked[i].height !== image.height) {
        throw new Error('Image changed during preflight.');
      }
    });
  }
  if (outPath) {
    for (const item of evidence.values()) {
      if (sameFile(outPath, item.file) || sameFile(outPath, item.recordPath)) throw new Error('Output aliases evidence.');
    }
  }
  return { refs, evidence, assets, occurrences, texts };
}
function load(options) {
  const bytes = fs.readFileSync(options.dataPath);
  const inputHash = digest(bytes);
  if (options.expectedHash && inputHash !== options.expectedHash) throw new Error('Report JSON changed since staging.');
  const data = parseJson(bytes.toString('utf8'));
  return { data, inputHash, report: inspectReport(data, options.root, options.dataPath, options.outPath) };
}
function manifest(data, report, inputHash) {
  return { schema: 1, input_sha256: inputHash, texts: report.texts, citationOccurrences: report.occurrences,
    chapterIds: data.chapters.map(ch => ch.id), references: [...report.refs.values()],
    assets: [...report.assets.values()].map(({ buffer, ...info }) => info),
    evidence: [...report.evidence.values()] };
}
module.exports = { NOTICE, PAGE, IMAGE_BOX, digest, parseJson, noLinks, within, local, sameFile, argumentsFor,
  inlineTokens, plainLabel, inspectReport, load, manifest };
if (require.main === module) {
  try {
    const { data, report, inputHash } = load(argumentsFor(process.argv, false));
    console.log(JSON.stringify(manifest(data, report, inputHash)));
  } catch (error) {
    console.error(`ERROR: report contract incomplete: ${error.message}`);
    process.exitCode = 2;
  }
}
