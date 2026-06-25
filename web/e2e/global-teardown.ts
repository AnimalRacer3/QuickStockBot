export default async function globalTeardown() {
  if (global.__MOCK_RELAY_WSS__) {
    await new Promise<void>((resolve) => {
      global.__MOCK_RELAY_WSS__.close(() => resolve());
    });
    console.log("[e2e] Mock relay stopped");
  }
}
