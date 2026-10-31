import { DurableObject } from "cloudflare:workers";

const PORT = 8080;
const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;

const PUBLIC_ENV = [
  "BNB_RPS",
  "BNB_ENABLED",
  "DEFAULT_EVM_CHAIN",
  "FLAP_BNB_ENABLED",
  "GENIUS_BNB_ENABLED",
  "ROBINHOOD_ENABLED",
  "SOLANA_ENABLED",
  "DRAW_DB_PATH",
  "OPMEM_DB_PATH",
  "DRAW_ENABLED",
  "REWARDS_ENABLED",
  "ALERTS_ENABLED",
  "REPLAY_ENABLED",
  "OPMEM_ENABLED",
  "BANKR_ENABLED",
  "BANKR_INDEX_ENABLED",
  "MAX_CONCURRENT",
  "SCAN_QUEUE_MAX",
  "SCAN_RATE_PER_MIN",
];

export class FoxscanContainer extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    const container = ctx.container;
    if (container?.running) {
      void ctx.blockConcurrencyWhile(() =>
        container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS),
      );
    }
  }

  async fetch(request) {
    this.starting ??= this.startAndWaitForPort(request).finally(() => {
      this.starting = undefined;
    });
    await this.starting;

    const url = new URL(request.url);
    url.protocol = "http:";
    url.host = "container";
    const forwarded = new Request(url, request);
    forwarded.headers.delete("host");
    return this.ctx.container.getTcpPort(PORT).fetch(forwarded);
  }

  async startAndWaitForPort(request) {
    const container = this.ctx.container;
    if (!container.running) {
      const env = {
        PORT: String(PORT),
        HOST: "0.0.0.0",
        SITE_URL: new URL(request.url).origin,
      };
      for (const key of PUBLIC_ENV) {
        const value = this.env[key];
        if (value) env[key] = value;
      }
      if (this.env.BNB_RPC) env.BNB_RPC = this.env.BNB_RPC;
      container.start({
        image: container.images.base,
        instance: "basic",
        enableInternet: true,
        env,
      });
    }
    await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);

    const port = container.getTcpPort(PORT);
    let lastError;
    for (let attempt = 0; attempt < 90; attempt++) {
      try {
        const response = await port.fetch("http://container/health", {
          signal: AbortSignal.timeout(1000),
        });
        await response.body?.cancel();
        if (!response.ok) {
          throw new Error(`Health check returned ${response.status}`);
        }
        return;
      } catch (error) {
        lastError = error;
        await scheduler.wait(1000);
      }
    }
    throw new Error("FoxScanner container did not become ready", { cause: lastError });
  }
}

export default {
  fetch(request, env) {
    return env.FOXSCAN.getByName("foxscan").fetch(request);
  },
};
