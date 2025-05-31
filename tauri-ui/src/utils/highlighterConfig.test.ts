import { describe, it, expect } from 'vitest';
import { highlighterConfig } from './highlighterConfig';

describe('highlighterConfig', () => {
  it('has all expected languages', () => {
    expect(Object.keys(highlighterConfig)).toEqual(
      expect.arrayContaining([
        'python',
        'tsx',
        'javascript',
        'html',
        'css'
      ])
    );
  });

  it('each language has an array of rules with name and pattern', () => {
    for (const [_lang, rules] of Object.entries(highlighterConfig)) {
      expect(Array.isArray(rules)).toBe(true);
      for (const rule of rules) {
        expect(typeof rule.name).toBe('string');
        expect(rule.pattern).toBeInstanceOf(RegExp);
      }
    }
  });

  it('python rules match code', () => {
    const rules = highlighterConfig['python'];
    const code = `
# comment
def foo(bar):
    print("hello", 123)
    # another comment
`;
    // Should match comment
    expect(code.match(rules.find(r => r.name === 'comment')!.pattern)).toContain('# comment');
    // Should match string
    expect(code.match(rules.find(r => r.name === 'string')!.pattern)).toContain('"hello"');
    // Should match number
    expect(code.match(rules.find(r => r.name === 'number')!.pattern)).toContain('123');
    // Should match keyword
    expect(code.match(rules.find(r => r.name === 'keyword')!.pattern)).toContain('def');
    // Should match builtin
    expect(code.match(rules.find(r => r.name === 'builtin')!.pattern)).toContain('print');
    // Should match method (should NOT match here)
    expect(code.match(rules.find(r => r.name === 'method')!.pattern)).toBeNull();
  });

  it('tsx rules match code', () => {
    const rules = highlighterConfig['tsx'];
    const code = `
import React from 'react';
// comment
interface Props { value: string }
const value = 42;
window.console.log('hi');
/* multi
   line */
    `;
    // Keyword
    expect(code.match(rules.find(r => r.name === 'keyword')!.pattern)).toContain('import');
    // String
    expect(code.match(rules.find(r => r.name === 'string')!.pattern)).toContain("'react'");
    // Number
    expect(code.match(rules.find(r => r.name === 'number')!.pattern)).toContain('42');
    // Builtin
    expect(code.match(rules.find(r => r.name === 'builtin')!.pattern)).toContain('window');
    // Method
    expect(code.match(rules.find(r => r.name === 'method')!.pattern)).toContain('.log');
    // Comment
    expect(code.match(rules.find(r => r.name === 'comment')!.pattern)).toContain('// comment');
  });

  it('javascript rules match code', () => {
    const rules = highlighterConfig['javascript'];
    const code = `const x = 5; // comment\nconsole.log(x);`;
    expect(code.match(rules.find(r => r.name === 'keyword')!.pattern)).toContain('const');
    expect(code.match(rules.find(r => r.name === 'number')!.pattern)).toContain('5');
    expect(code.match(rules.find(r => r.name === 'builtin')!.pattern)).toContain('console');
    expect(code.match(rules.find(r => r.name === 'method')!.pattern)).toContain('.log');
    expect(code.match(rules.find(r => r.name === 'comment')!.pattern)).toContain('// comment');
  });

  it('html rules match code', () => {
    const rules = highlighterConfig['html'];
    const code = '&lt;!-- comment --&gt;&lt;div id="x"&gt;"hi"&lt;/div&gt;';
    expect(code.match(rules.find(r => r.name === 'comment')!.pattern)).toContain('&lt;!-- comment --&gt;');
    expect(code.match(rules.find(r => r.name === 'keyword')!.pattern)).not.toBeNull();
    expect(code.match(rules.find(r => r.name === 'string')!.pattern)).not.toBeNull();
    expect(code.match(rules.find(r => r.name === 'builtin')!.pattern)).not.toBeNull();
  });

  it('css rules match code', () => {
    const rules = highlighterConfig['css'];
    const code = `body { color: #fff; /* comment */ font-size: 14px; }`;
    expect(code.match(rules.find(r => r.name === 'comment')!.pattern)).toContain('/* comment */');
    expect(code.match(rules.find(r => r.name === 'keyword')!.pattern)).toContain('body');
    expect(code.match(rules.find(r => r.name === 'builtin')!.pattern)).toContain('color');
    expect(code.match(rules.find(r => r.name === 'string')!.pattern)).toContain('#fff');
    expect(code.match(rules.find(r => r.name === 'number')!.pattern)).toContain('14px');
  });
});
