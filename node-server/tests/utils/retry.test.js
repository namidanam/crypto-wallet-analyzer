import { jest } from '@jest/globals';
import { retryWithBackoff } from '../../src/utils/retry.js';

describe('Retry Utility', () => {
  it('should retry until success', async () => {
    let count = 0;

    const fn = jest.fn(() => {
      if (count++ < 2) {
        const err = new Error('fail');
        err.code = 'ECONNRESET'; // 👈 make it retriable
        throw err;
      }
      return 'success';
    });

    const result = await retryWithBackoff(fn, 3, {
      initialDelayMs: 0 // 👈 avoid waiting during tests
    });

    expect(result).toBe('success');
    expect(fn).toHaveBeenCalledTimes(3);
  });
});