import '@testing-library/preact';
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// A generic always-resolved fetch mock. You can add smarter logic if needed!
globalThis.fetch = vi.fn(async (...args) => {
  return {
    ok: true,
    status: 200,
    json: async () => ({}),
    text: async () => '',
    // add .body, .clone(), etc if you test streams!
  } as any;
});
