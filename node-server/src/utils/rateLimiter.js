let lastCall = 0;

async function rateLimit() {

  const now = Date.now();
  const diff = now - lastCall;
  const minInterval = 200; // 5 requests/sec

  if (diff < minInterval) {
    await new Promise(res =>
      setTimeout(res, minInterval - diff)
    );
  }

  lastCall = Date.now();
}

export { rateLimit };