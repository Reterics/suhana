import { highlighterConfig } from './highlighterConfig';

export function highlightCode(language: string, rawCode: string): string {
  const escape = (text: string) =>
    text.replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

  const rules = highlighterConfig[language];
  if (!rules) return escape(rawCode);

  let segments: { text: string; className?: string }[] = [{ text: rawCode }];

  for (const { name, pattern } of rules) {
    const newSegments: typeof segments = [];

    for (const segment of segments) {
      if (segment.className) {
        newSegments.push(segment);
        continue;
      }

      let lastIndex = 0;
      for (const match of [...segment.text.matchAll(pattern)]) {
        const index = match.index!;
        const matchedText = match[0];

        if (index > lastIndex) {
          newSegments.push({ text: segment.text.slice(lastIndex, index) });
        }

        newSegments.push({ text: matchedText, className: name });
        lastIndex = index + matchedText.length;
      }

      if (lastIndex < segment.text.length) {
        newSegments.push({ text: segment.text.slice(lastIndex) });
      }
    }

    segments = newSegments;
  }

  return segments.map(seg =>
    seg.className
      ? `<span class="${seg.className}">${escape(seg.text)}</span>`
      : escape(seg.text)
  ).join('');
}

