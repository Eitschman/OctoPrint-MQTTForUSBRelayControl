export function validateTarget(target: string | undefined): void {
  if (!target) return;
  const parsed = new URL(target);
  if (
    parsed.protocol !== "http:" ||
    parsed.hostname !== "127.0.0.1" ||
    !parsed.port ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== "/" ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      "Browser tests require a disposable loopback HTTP target with an explicit port",
    );
  }
}

export function requireCredentials(
  username: string | undefined,
  password: string | undefined,
): void {
  if (!username || !password)
    throw new Error("Generated disposable test credentials are required");
}
