#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const contract = require('./report_contract');
const esc = value => String(value).replace(/[&<>"']/g,
  ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);

function main() {
  const options = contract.argumentsFor(process.argv);
  const { data, report } = contract.load(options);
  const occurrences = new Map();
  const inline = value => contract.inlineTokens(value).map(token => {
    if (token.refId !== undefined) {
      const count = (occurrences.get(token.refId) || 0) + 1;
      occurrences.set(token.refId, count);
      return `<a class="ref" id="body-ref-${token.refId}${count === 1 ? '' : '-' + count}" href="#ref-${token.refId}"><sup>${token.refId}</sup></a>`;
    }
    let rendered = esc(token.text);
    if (token.italic) rendered = `<em>${rendered}</em>`;
    if (token.bold) rendered = `<strong>${rendered}</strong>`;
    return rendered;
  }).join('');
  const sections = [];
  for (const chapter of data.chapters) {
    const content = [`<h1>${inline(chapter.title)}</h1>`];
    for (const section of chapter.sections) {
      if (section.type === 'image') {
        const image = report.assets.get(section);
        content.push(`<figure data-evidence="${esc(image.evidenceId)}"><img alt="${esc(image.caption)}" width="${image.renderedWidth}" height="${image.renderedHeight}" src="data:image/${image.type === 'jpg' ? 'jpeg' : 'png'};base64,${image.buffer.toString('base64')}"><figcaption><p class="caption">${inline(section.caption)}</p><p class="source">${inline(section.source)}</p></figcaption></figure>`);
      } else if (section.type === 'quote') {
        content.push(`<blockquote><p>${inline(section.text)}</p><cite>${inline(section.attribution)}</cite></blockquote>`);
      } else if (section.type === 'bullet') {
        content.push(`<ul><li>${inline(section.text)}</li></ul>`);
      } else {
        const tag = ['h2', 'h3'].includes(section.type) ? section.type : 'p';
        content.push(`<${tag}>${inline(section.text)}</${tag}>`);
      }
    }
    sections.push(`<section class="chapter" id="${esc(chapter.id)}">${content.join('\n')}</section>`);
  }
  const references = data.references.map(ref =>
    `<li id="ref-${ref.id}" value="${ref.id}"><span class="reference-text">${inline(`${ref.id}. ${ref.long}`)}</span> <a class="back" href="#body-ref-${ref.id}" aria-label="Back to first citation">Back</a></li>`).join('\n');
  const body = `<header><h1>${esc(data.meta.title)}</h1><p>${esc(`Prepared by ${data.meta.author}`)}</p><p>${esc(`Round ${data.meta.round}; ${data.meta.date}`)}</p><p class="notice">${esc(contract.NOTICE)}</p></header>
<main>${sections.join('\n')}<section id="references"><h1>References</h1><ol class="references">${references}</ol></section></main>`;
  const templatePath = path.join(__dirname, '..', 'assets', 'html-template.html');
  if (contract.sameFile(templatePath, options.outPath)) throw new Error('Output aliases the HTML template.');
  const template = fs.readFileSync(templatePath, 'utf8');
  if (template.split('{{TITLE}}').length !== 2 || template.split('{{BODY}}').length !== 2) throw new Error('Invalid HTML template placeholders.');
  const html = template.replace(/\{\{(TITLE|BODY)\}\}/g,
    (_match, slot) => slot === 'TITLE' ? esc(data.meta.title) : body);
  fs.writeFileSync(options.outPath, html, { flag: 'wx' });
}
try { main(); } catch (error) {
  console.error(`ERROR: HTML generation incomplete: ${error.message}`);
  process.exitCode = 2;
}
