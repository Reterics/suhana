import { render, screen, fireEvent } from '@testing-library/preact';
import { describe, it, expect, vi } from 'vitest';
import { ProjectMetadata } from './ProjectMetadata';

// Mock icons
vi.mock('lucide-preact', () => ({
  ChevronDown: () => <span data-testid="icon-down" />,
  ChevronRight: () => <span data-testid="icon-right" />,
  Code: () => <span data-testid="icon-code" />,
  __esModule: true,
}));

describe('ProjectMetadata', () => {
  it('renders nothing when metadata is null', () => {
    const { container } = render(<ProjectMetadata metadata={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders simple fields (primitives)', () => {
    render(
      <ProjectMetadata
        metadata={{
          project_type: 'node',
          version: '1.0.0',
          count: 42,
          ready: true,
          name: 'My Project', // should be skipped
        }}
      />
    );
    expect(screen.getByText('project_type:')).toBeTruthy();
    expect(screen.getByText('node')).toBeTruthy();
    expect(screen.getByText('version:')).toBeTruthy();
    expect(screen.getByText('1.0.0')).toBeTruthy();
    expect(screen.getByText('count:')).toBeTruthy();
    expect(screen.getByText('42')).toBeTruthy();
    expect(screen.getByText('ready:')).toBeTruthy();
    expect(screen.getByText('true')).toBeTruthy();
    // "name" should not be rendered
    expect(screen.queryByText('name:')).toBeNull();
  });

  it('renders array fields collapsed and expands on click', () => {
    render(
      <ProjectMetadata
        metadata={{
          dependencies: ['a', 'b', 'c'],
        }}
      />
    );
    // Collapsed indicator
    expect(screen.getByText('dependencies:')).toBeTruthy();
    expect(screen.getByText('[3 items]')).toBeTruthy();
    expect(screen.getByTestId('icon-right')).toBeTruthy();
    // Expand array
    fireEvent.click(screen.getByText('dependencies:').closest('div')!);
    expect(screen.getByTestId('icon-down')).toBeTruthy();
    // Items now rendered
    expect(screen.getByText('a')).toBeTruthy();
    expect(screen.getByText('b')).toBeTruthy();
    expect(screen.getByText('c')).toBeTruthy();
  });

  it('renders object fields collapsed and expands on click', () => {
    render(
      <ProjectMetadata
        metadata={{
          config: { a: 1, b: 'two', c: { d: 3 } },
        }}
      />
    );
    // Collapsed
    expect(screen.getByText('config:')).toBeTruthy();
    expect(screen.getByText('{...}')).toBeTruthy();
    expect(screen.getByTestId('icon-right')).toBeTruthy();
    // Expand
    fireEvent.click(screen.getByText('config:').closest('div')!);
    expect(screen.getByTestId('icon-down')).toBeTruthy();
    // Object fields
    expect(screen.getByText('a:')).toBeTruthy();
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByText('b:')).toBeTruthy();
    expect(screen.getByText('two')).toBeTruthy();
    expect(screen.getByText('c:')).toBeTruthy();
    expect(screen.getByText(/"d":3/)).toBeTruthy(); // JSON.stringify for nested
  });

  it('supports nested arrays and objects', () => {
    render(
      <ProjectMetadata
        metadata={{
          nested: [
            { foo: 'bar' },
            { baz: [1, 2] },
          ],
        }}
      />
    );
    // Collapsed
    expect(screen.getByText('nested:')).toBeTruthy();
    fireEvent.click(screen.getByText('nested:').closest('div')!);
    expect(screen.getByText('{"foo":"bar"}')).toBeTruthy();
    expect(screen.getByText('{"baz":[1,2]}')).toBeTruthy();
  });

  it('renders nothing for empty metadata', () => {
    const { container } = render(<ProjectMetadata metadata={{}} />);
    expect(container.textContent).toBe('');
  });
});
