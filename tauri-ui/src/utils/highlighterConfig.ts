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
  ],
  typescript: [
    { name: 'comment', pattern: /(\/\/.*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /(["'`])(?:\\[\s\S]|(?!\1).)*\1/g },
    { name: 'number', pattern: /\b\d+(\.\d+)?\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(const|let|var|function|return|if|else|switch|case|default|for|while|do|break|continue|try|catch|finally|throw|import|from|export|new|class|extends|this|typeof|instanceof|in|of|interface|type|implements|enum|abstract|public|private|protected|readonly|declare|namespace|module|as|satisfies|infer|keyof|await|async|never|unknown|any|void|bigint|symbol)\b/g
    },
    {
      name: 'builtin',
      pattern:
        /\b(Array|Promise|Record|Partial|Pick|Omit|Required|Readonly|ReturnType|Parameters|NonNullable|Exclude|Extract|Map|Set|WeakMap|WeakSet|string|number|boolean|any|unknown|never|null|undefined|void|bigint|symbol)\b/g
    },
    { name: 'method', pattern: /\.(\w+)\s*(?=\()?/g }
  ],
  rust: [
    { name: 'comment', pattern: /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /b?"(?:\\.|[^"\\\n])*"|r(#*)"(?:[\s\S]*?)"\1/g },
    { name: 'number', pattern: /\b(?:0x[0-9A-Fa-f_]+|0o[0-7_]+|0b[01_]+|\d[\d_]*(?:\.\d[\d_]*)?)(?:[iu](?:8|16|32|64|128|size)|f(?:32|64))?\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(fn|let|mut|struct|enum|trait|impl|for|in|if|else|match|while|loop|break|continue|return|use|mod|pub|crate|super|self|Self|as|where|move|ref|type|const|static|unsafe|async|await|dyn|extern)\b/g
    },
    {
      name: 'builtin',
      pattern:
        /\b(Option|Result|Some|None|Ok|Err|String|str|Vec|Box|Cow|Rc|Arc|HashMap|HashSet|usize|isize|u8|u16|u32|u64|u128|i8|i16|i32|i64|i128|f32|f64|bool|char)\b/g
    },
    { name: 'method', pattern: /\b([\w:]+)!|\.(\w+)\s*(?=\()?/g },
    { name: 'keyword', pattern: /#\[(?:\\.|[^\]])*\]/g }
  ],
  json: [
    { name: 'comment', pattern: /(\/\/.*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /"(?:\\.|[^"\\\n])*"/g },
    { name: 'number', pattern: /-?\b\d+(\.\d+)?([eE][+-]?\d+)?\b/g },
    { name: 'builtin', pattern: /\b(true|false|null)\b/g },
    { name: 'keyword', pattern: /"(?:\\.|[^"\\\n])*"(?=\s*:)/g }
  ],

  bash: [
    { name: 'comment', pattern: /(^|\s)#.*$/gm },
    { name: 'string', pattern: /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g },
    { name: 'number', pattern: /\b\d+\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(if|then|elif|else|fi|for|while|until|do|done|case|esac|function|select|in|time|coproc|break|continue|return|exit)\b/g
    },
    {
      name: 'builtin',
      pattern:
        /\b(echo|cd|pwd|ls|grep|awk|sed|cut|tr|tee|cat|head|tail|chmod|chown|curl|wget|tar|zip|unzip|export|alias|unalias|type|hash|printf|read|test|[`$][\w?@#*!-]+)\b/g
    },
    { name: 'method', pattern: /\$[A-Za-z_]\w*|\$\{[^}]+\}|\$\((?:[^)(]|\([^)(]*\))*\)|`[^`]*`/g }
  ],
  sql: [
    { name: 'comment', pattern: /(--[^\n]*|\/\*[\s\S]*?\*\/)/g },
    { name: 'string', pattern: /'(?:''|[^'])*'/g },
    { name: 'number', pattern: /\b\d+(\.\d+)?\b/g },
    {
      name: 'keyword',
      pattern:
        /\b(SELECT|FROM|WHERE|AND|OR|NOT|NULL|IS|IN|EXISTS|BETWEEN|LIKE|ILIKE|GROUP|BY|ORDER|ASC|DESC|LIMIT|OFFSET|JOIN|INNER|LEFT|RIGHT|FULL|OUTER|ON|AS|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|VIEW|INDEX|DROP|ALTER|ADD|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|CHECK|DEFAULT|DISTINCT|HAVING|WITH|CTE|CASE|WHEN|THEN|ELSE|END)\b/gi
    },
    {
      name: 'builtin',
      pattern:
        /\b(COUNT|SUM|AVG|MIN|MAX|NOW|CURRENT_DATE|CURRENT_TIME|CURRENT_TIMESTAMP|COALESCE|NVL|LENGTH|LOWER|UPPER|SUBSTR|ROUND|CAST|CONVERT)\b/gi
    },
    { name: 'method', pattern: /\.(\w+)\s*(?=\()?/g }
  ]
};
