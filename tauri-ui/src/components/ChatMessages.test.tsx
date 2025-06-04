import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/preact';
import { ChatMessages } from './ChatMessages';

// -- Mock CodeBlock for simplicity --
vi.mock('./CodeBlock.tsx', () => ({
  CodeBlock: ({ code, lang }: any) => (
    <pre data-testid="codeblock">
      {lang}:{code}
    </pre>
  ),
  __esModule: true
}));

describe('ChatMessages', () => {
  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn()
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing for empty messages', () => {
    const { container } = render(<ChatMessages messages={[]} />);
    expect(container).toHaveTextContent('');
  });

  it('renders a plain text message', () => {
    render(<ChatMessages messages={[{ role: 'user', content: 'Hello!' }]} />);
    // Should be right-aligned
    const msg = screen.getByText('Hello!');
    expect(msg).toBeVisible();
    expect(msg.parentElement?.parentElement).toHaveClass('text-right');
  });

  it('renders an assistant message left-aligned', () => {
    render(
      <ChatMessages
        messages={[{ role: 'assistant', content: 'How can I help?' }]}
      />
    );

    const msg = screen.getByText('How can I help?');
    expect(msg).toBeVisible();
    expect(msg.parentElement?.parentElement).toHaveClass('text-left');
  });

  it('renders code blocks and text fragments', () => {
    const msg = `Here is code:\n\`\`\`js\nconsole.log("hi")\n\`\`\`\nDid you like it?`;
    render(<ChatMessages messages={[{ role: 'assistant', content: msg }]} />);
    // Code block present
    const codeBlock = screen.getByTestId('codeblock');
    expect(codeBlock).toHaveTextContent('js:console.log("hi")');
    // Text fragments present
    expect(screen.getByText('Here is code:')).toBeTruthy();
    expect(screen.getByText('Did you like it?')).toBeTruthy();
  });

  it('renders multiple code blocks in one message', () => {
    const msg = [
      'Example:',
      '```python\nprint(1)\n```',
      'Middle text.',
      '```bash\necho ok\n```',
      'End.'
    ].join('\n');
    render(<ChatMessages messages={[{ role: 'assistant', content: msg }]} />);
    const codeBlocks = screen.getAllByTestId('codeblock');
    expect(codeBlocks.length).toBe(2);
    expect(codeBlocks[0]).toHaveTextContent('python:print(1)');
    expect(codeBlocks[1]).toHaveTextContent('bash:echo ok');
    expect(screen.getByText('Example:')).toBeTruthy();
    expect(screen.getByText('Middle text.')).toBeTruthy();
    expect(screen.getByText('End.')).toBeTruthy();
  });

  it('auto-scrolls on new messages (smoke test)', () => {
    // The scrollIntoView call is not visible, but we can spy on it
    const scrollSpy = vi.fn();
    // Provide a fake ref implementation
    Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollSpy
    });

    const { rerender } = render(
      <ChatMessages messages={[{ role: 'user', content: 'Hi' }]} />
    );
    // Initial call
    rerender(
      <ChatMessages
        messages={[
          { role: 'user', content: 'Hi' },
          { role: 'assistant', content: 'Hello' }
        ]}
      />
    );
    // The scrollIntoView should have been called
    expect(scrollSpy).toHaveBeenCalled();
  });
});
