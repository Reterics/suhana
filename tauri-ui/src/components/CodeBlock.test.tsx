import { render } from 'preact';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CodeBlock } from './CodeBlock.tsx';
import * as highlightCodeModule from '../utils/highlightCode.ts';

// Mock the highlightCode function
vi.mock('../utils/highlightCode', () => ({
  highlightCode: vi.fn((lang, code) => `mocked-highlight-${lang}-${code}`)
}));

describe('CodeBlock Component', () => {
  // Reset mocks before each test
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock clipboard API
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: vi.fn().mockImplementation(() => Promise.resolve())
      },
      writable: true
    });
    // Clear the document body before each test
    document.body.innerHTML = '';
  });

  it('renders with the correct language label', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    render(<CodeBlock code="const x = 1;" lang="javascript" />, container);

    // Check if the language label is displayed correctly
    const languageLabel = container.querySelector('.language-label');
    expect(languageLabel?.textContent?.trim()).toBe('javascript');
  });

  it('displays "Unknown Language" when no language is provided', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    render(<CodeBlock code="some code" lang="" />, container);

    // Check if "Unknown Language" is displayed when no language is provided
    const languageLabel = container.querySelector('.language-label');
    expect(languageLabel?.textContent?.trim()).toBe('Unknown Language');
  });

  it('calls highlightCode with the correct parameters', () => {
    const code = 'const x = 1;';
    const lang = 'javascript';
    const container = document.createElement('div');
    document.body.appendChild(container);

    render(<CodeBlock code={code} lang={lang} />, container);

    // Check if highlightCode was called with the correct parameters
    expect(highlightCodeModule.highlightCode).toHaveBeenCalledWith(lang, code.trim());
  });

  it('copies code to clipboard when copy button is clicked', async () => {
    const code = 'const x = 1;';
    const container = document.createElement('div');
    document.body.appendChild(container);

    render(<CodeBlock code={code} lang="javascript" />, container);

    // Find and click the copy button
    const copyButton = container.querySelector('.copy-btn');
    copyButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    // Check if clipboard.writeText was called with the correct code
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(code);
  });

  it('applies the correct CSS class for the language', () => {
    const lang = 'python';
    const container = document.createElement('div');
    document.body.appendChild(container);

    render(<CodeBlock code="def hello(): pass" lang={lang} />, container);

    // Check if the code element has the correct language class
    const codeElement = container.querySelector(`code.language-${lang}`);
    expect(codeElement).not.toBeNull();
  });
});
