import { describe, it, expect, vi } from 'vitest';

// Mock highlighterConfig with a simple syntax
vi.mock('./highlighterConfig', () => ({
  highlighterConfig: {
    js: [
      { name: 'keyword', pattern: /\b(?:const|let|var|function)\b/g },
      { name: 'number', pattern: /\b\d+\b/g }
    ],
    py: [
      { name: 'keyword', pattern: /\bdef\b/g },
      { name: 'string', pattern: /'[^']*'/g }
    ]
  }
}));

import { highlightCode } from './highlightCode';

describe('highlightCode', () => {
  it('returns code with keywords and numbers highlighted for JS', () => {
    const result = highlightCode('js', 'const x = 42;');
    // Should highlight "const" and "42"
    expect(result).toContain('<span class="keyword">const</span>');
    expect(result).toContain('<span class="number">42</span>');
    expect(result).toContain('x = ');
    // No double-escaping
    expect(result).not.toContain('<span class="keyword">&lt;');
  });

  it('returns code with keywords and strings highlighted for Python', () => {
    const code = "def foo(): return 'bar'";
    const result = highlightCode('py', code);
    expect(result).toContain('<span class="keyword">def</span>');
    expect(result).toContain('<span class="string">\'bar\'</span>');
    expect(result).toContain('foo(): return ');
  });

  it('escapes HTML characters', () => {
    const result = highlightCode('js', 'const x = "<tag>";');
    // <tag> should become &lt;tag&gt;
    expect(result).toContain('&lt;tag&gt;');
    // Only in the correct position, not double-escaped
    expect(result).toContain('<span class="keyword">const</span>');
  });

  it('returns escaped code if language not found', () => {
    const code = 'alert("hi"); <b>bold</b>';
    const result = highlightCode('unknownlang', code);
    expect(result).toBe('alert("hi"); &lt;b&gt;bold&lt;/b&gt;');
  });

  it('handles overlapping rules by applying in order', () => {
    // "const 42" should highlight both "const" and "42"
    const result = highlightCode('js', 'const 42');
    expect(result).toContain(
      '<span class="keyword">const</span> <span class="number">42</span>'
    );
  });

  it('does not crash on empty code', () => {
    expect(highlightCode('js', '')).toBe('');
    expect(highlightCode('notfound', '')).toBe('');
  });

  it('handles code with no matches', () => {
    const code = 'foo bar baz';
    const result = highlightCode('js', code);
    // No <span>
    expect(result).not.toContain('<span');
    expect(result).toBe('foo bar baz');
  });
});
