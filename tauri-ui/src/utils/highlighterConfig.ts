export interface HighlightRule {
  name: string;
  pattern: RegExp;
}

export const highlighterConfig: Record<string, HighlightRule[]> = {
  python: [
    { name: 'comment', pattern: /(#.*)/g },
    {
      name: 'string',
      pattern: /("""[\s\S]*?"""|'''[\s\S]*?'''|"[^"\n]*"|'[^'\n]*')/g
    },
    { name: 'number', pattern: /\b(\d+(\.\d+)?)\b/g },
    {
      name: 'builtin',
      pattern: /\b(print|len|range|int|str|list|dict|set|float|type)\b/g
    },
    {
      name: 'keyword',
      pattern:
        /\b(def|class|import|from|as|if|elif|else|while|for|in|return|try|except|finally|with|yield|lambda|not|and|or|is|None|True|False)\b/g
    },
    { name: 'method', pattern: /\.(\w+)\s*(?=\()?/g }
  ],
  tsx: [
    { name: 'comment', pattern: /(\/\/.*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /(["'`])(?:\\[\s\S]|(?!\1).)*\1/g },
    { name: 'number', pattern: /\b\d+(\.\d+)?\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(const|let|var|function|return|if|else|for|while|import|from|as|export|interface|type|extends|implements|new|class)\b/g
    },
    {
      name: 'builtin',
      pattern:
        /\b(console|document|window|Math|Date|JSON|Array|String|Number|Boolean)\b/g
    },
    { name: 'method', pattern: /\.(\w+)\s*(?=\()?/g }
  ],
  javascript: [
    { name: 'comment', pattern: /(\/\/.*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /(["'`])(?:\\[\s\S]|(?!\1).)*\1/g },
    { name: 'number', pattern: /\b\d+(\.\d+)?\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(const|let|var|function|return|if|else|switch|case|default|for|while|do|break|continue|try|catch|finally|throw|await|async|import|from|export|new|class|extends|this|typeof|instanceof|in|of)\b/g
    },
    {
      name: 'builtin',
      pattern:
        /\b(console|window|document|Array|String|Object|Math|Date|JSON|Promise|Set|Map|Boolean|Number)\b/g
    },
    { name: 'method', pattern: /\.(\w+)\s*(?=\()?/g }
  ],
  html: [
    { name: 'keyword', pattern: /(&lt;\/?[a-zA-Z][^\s&<>]*?)(?=\s|&gt;)/g },
    { name: 'builtin', pattern: /\b([a-zA-Z-:]+)(?==)/g },
    { name: 'string', pattern: /"(.*?)"|'(.*?)'/g },
    { name: 'comment', pattern: /&lt;!--[\s\S]*?--&gt;/g }
  ],
  css: [
    { name: 'comment', pattern: /\/\*[\s\S]*?\*\//g },
    { name: 'keyword', pattern: /[.#]?[a-zA-Z_][\w-]*(?=\s*\{)/g },
    { name: 'builtin', pattern: /\b[a-z-]+(?=\s*:)/g },
    { name: 'string', pattern: /"(.*?)"|'(.*?)'|#[\da-fA-F]{3,6}/g },
    { name: 'number', pattern: /\b\d+(\.\d+)?(px|em|rem|%)?\b/g }
  ]
};
