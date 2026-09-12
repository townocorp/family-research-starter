#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const contract = require('./report_contract');
const { Document, Packer, Paragraph, TextRun, ImageRun, HeadingLevel, AlignmentType } = require('docx');

function runs(value) {
  return contract.inlineTokens(value).map(token => new TextRun(token.refId === undefined
    ? { text: token.text, bold: !!token.bold, italics: !!token.italic }
    : { text: String(token.refId), superScript: true }));
}
function paragraph(value, options = {}) {
  return new Paragraph({ spacing: { after: 180 }, ...options, children: runs(value) });
}
async function main() {
  const options = contract.argumentsFor(process.argv);
  const { data, report } = contract.load(options);
  const children = [
    new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(data.meta.title)] }),
    new Paragraph({ children: [new TextRun(`Prepared by ${data.meta.author}`)] }),
    new Paragraph({ children: [new TextRun(`Round ${data.meta.round}; ${data.meta.date}`)] }),
    paragraph(contract.NOTICE),
  ];
  for (const chapter of data.chapters) {
    children.push(paragraph(chapter.title, { heading: HeadingLevel.HEADING_1 }));
    for (const section of chapter.sections) {
      if (section.type === 'image') {
        const image = report.assets.get(section);
        children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [
          new ImageRun({ type: image.type, data: image.buffer,
            transformation: { width: image.renderedWidth, height: image.renderedHeight },
            altText: { title: image.evidenceId, description: image.caption, name: image.evidenceId } }),
        ] }));
        children.push(paragraph(section.caption, { style: 'Caption', keepNext: true, keepLines: true }));
        children.push(paragraph(section.source, { style: 'EvidenceSource', keepLines: true }));
      } else if (section.type === 'quote') {
        children.push(paragraph(section.text, { indent: { left: 480, right: 480 } }));
        children.push(paragraph(section.attribution, { style: 'EvidenceSource' }));
      } else {
        const extra = section.type === 'h2' ? { heading: HeadingLevel.HEADING_2 }
          : section.type === 'h3' ? { heading: HeadingLevel.HEADING_3 }
          : section.type === 'bullet' ? { bullet: { level: 0 } } : {};
        children.push(paragraph(section.text, extra));
      }
    }
  }
  children.push(paragraph('References', { heading: HeadingLevel.HEADING_1 }));
  for (const ref of data.references) children.push(paragraph(`${ref.id}. ${ref.long}`));
  const document = new Document({
    creator: data.meta.author, title: data.meta.title, description: contract.NOTICE,
    styles: {
      default: { document: { run: { font: 'Arial', size: 22 } } },
      paragraphStyles: [
        { id: 'Caption', name: 'Caption', basedOn: 'Normal', run: { italics: true, size: 20 } },
        { id: 'EvidenceSource', name: 'Evidence source', basedOn: 'Normal', run: { size: 18 } },
      ],
    },
    sections: [{ properties: { page: {
      size: { width: contract.PAGE.width, height: contract.PAGE.height },
      margin: { top: contract.PAGE.margin, right: contract.PAGE.margin,
        bottom: contract.PAGE.margin, left: contract.PAGE.margin },
    } }, children }],
  });
  const buffer = await Packer.toBuffer(document);
  fs.writeFileSync(options.outPath, buffer, { flag: 'wx' });
}
main().catch(error => {
  console.error(`ERROR: DOCX generation incomplete: ${error.message}`);
  process.exitCode = 2;
});
