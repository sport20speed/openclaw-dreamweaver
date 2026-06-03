import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const DREAMWEAVER_BASE = "http://127.0.0.1:8000";

async function apiGet(path: string): Promise<any> {
  const res = await fetch(`${DREAMWEAVER_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`DreamWeaver API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function apiPost(path: string, body?: any): Promise<any> {
  const res = await fetch(`${DREAMWEAVER_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`DreamWeaver API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function apiDelete(path: string): Promise<any> {
  const res = await fetch(`${DREAMWEAVER_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`DreamWeaver API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export default function (pi: ExtensionAPI) {
  // ── dream_status ──────────────────────────────────────────

  pi.registerTool({
    name: "dream_status",
    label: "DreamWeaver Status",
    description: "Check the current DreamWeaver dream state: status (idle/running/completed), current round, motif, best score, elapsed time.",
    promptSnippet: "Check DreamWeaver dream status, progress, and score.",
    promptGuidelines: [
      "Use dream_status to check whether DreamWeaver is idle or running and see the current dream's progress.",
    ],
    parameters: Type.Object({}),
    async execute() {
      const data = await apiGet("/dream/status");
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_start ───────────────────────────────────────────

  pi.registerTool({
    name: "dream_start",
    label: "DreamWeaver Start Dream",
    description:
      "Manually trigger a DreamWeaver dream session. Optionally provide a motif (theme/question to explore). If omitted, DreamWeaver auto-generates a motif based on recent user activity.",
    promptSnippet: "Start a new DreamWeaver dream with an optional motif.",
    promptGuidelines: [
      "Use dream_start to begin a new DreamWeaver self-play dream session on a given motif or theme.",
      "Some dreams require DeepSeek API credits; check with the user if you are unsure.",
    ],
    parameters: Type.Object({
      motif: Type.Optional(
        Type.String({ description: "Optional motif/theme for the dream. Example: '如何提升个人工作效率'" })
      ),
    }),
    async execute(_toolCallId, params) {
      const data = await apiPost("/dream/start", { motif: params.motif || null });
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_stop ────────────────────────────────────────────

  pi.registerTool({
    name: "dream_stop",
    label: "DreamWeaver Stop Dream",
    description: "Interrupt the currently running dream, save a checkpoint, and return intermediate results (motif, best score, iterations, convergence reason).",
    promptSnippet: "Stop the currently running DreamWeaver dream.",
    promptGuidelines: [
      "Use dream_stop to interrupt a running dream and get intermediate results.",
    ],
    parameters: Type.Object({}),
    async execute() {
      const data = await apiPost("/dream/stop");
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_history ─────────────────────────────────────────

  pi.registerTool({
    name: "dream_history",
    label: "DreamWeaver History",
    description: "List completed dreams with pagination. Returns dream ID, motif, best score, iteration count, status, and timestamps.",
    promptSnippet: "List DreamWeaver dream history.",
    promptGuidelines: [
      "Use dream_history to browse past dreams and their results.",
    ],
    parameters: Type.Object({
      limit: Type.Optional(
        Type.Number({ description: "Max results (default 20, max 100)" })
      ),
      offset: Type.Optional(
        Type.Number({ description: "Pagination offset" })
      ),
    }),
    async execute(_toolCallId, params) {
      const query = new URLSearchParams();
      if (params.limit) query.set("limit", String(params.limit));
      if (params.offset) query.set("offset", String(params.offset));
      const data = await apiGet(`/dream/history?${query.toString()}`);
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_detail ──────────────────────────────────────────

  pi.registerTool({
    name: "dream_detail",
    label: "DreamWeaver Dream Detail",
    description: "Get full details of a specific dream by ID, including all iteration logs (each round's prompt, response, score, and tokens used).",
    promptSnippet: "Get full details of a specific DreamWeaver dream.",
    promptGuidelines: [
      "Use dream_detail to inspect a specific dream's iteration-by-iteration evolution and logic.",
    ],
    parameters: Type.Object({
      dream_id: Type.String({ description: "Dream ID (e.g. from dream_history)" }),
    }),
    async execute(_toolCallId, params) {
      const data = await apiGet(`/dream/${encodeURIComponent(params.dream_id)}`);
      const dream = data.dream;
      const iterations = data.iterations || [];
      const summary =
        `Dream: ${dream.motif}\nStatus: ${dream.status}\nBest Score: ${dream.best_score ?? "-"}\nIterations: ${dream.iterations}\n\n` +
        iterations
          .slice(-10)
          .map(
            (it: any) =>
              `  Round ${it.round} [${it.role}]: score=${it.score ?? "-"} tokens=${it.tokens_used}`
          )
          .join("\n") +
        (iterations.length > 10 ? `\n  ... and ${iterations.length - 10} more rounds` : "");
      return {
        content: [{ type: "text", text: summary }],
        details: data,
      };
    },
  });

  // ── dream_delete ──────────────────────────────────────────

  pi.registerTool({
    name: "dream_delete",
    label: "DreamWeaver Delete Dream",
    description: "Remove a dream and its iteration logs from the database.",
    parameters: Type.Object({
      dream_id: Type.String({ description: "Dream ID to delete" }),
    }),
    async execute(_toolCallId, params) {
      const data = await apiDelete(`/dream/${encodeURIComponent(params.dream_id)}`);
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_apply ───────────────────────────────────────────

  pi.registerTool({
    name: "dream_apply",
    label: "DreamWeaver Mark Dream Applied",
    description: "Mark a dream as 'applied' (user has acted on its suggestions).",
    parameters: Type.Object({
      dream_id: Type.String({ description: "Dream ID to mark as applied" }),
    }),
    async execute(_toolCallId, params) {
      const data = await apiPost(`/dream/${encodeURIComponent(params.dream_id)}/apply`);
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── dream_config (read-only) ──────────────────────────────

  pi.registerTool({
    name: "dream_config",
    label: "DreamWeaver Config",
    description: "View DreamWeaver's current runtime configuration: models, limits, thresholds.",
    parameters: Type.Object({}),
    async execute() {
      const data = await apiGet("/dream/config");
      return {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        details: data,
      };
    },
  });

  // ── Command: /dream ────────────────────────────────────────

  pi.registerCommand("dream", {
    description: "Interact with DreamWeaver. Usage: /dream status | start [motif] | stop | history | detail <id>",
    handler: async (args, ctx) => {
      const parts = (args || "").trim().split(/\s+/);
      const sub = parts[0] || "status";
      try {
        switch (sub) {
          case "status": {
            const data = await apiGet("/dream/status");
            ctx.ui.notify(
              `DreamWeaver: ${data.status} | round ${data.current_round} | score ${data.best_score ?? "-"}`,
              "info"
            );
            break;
          }
          case "start": {
            const motif = parts.slice(1).join(" ") || undefined;
            const data = await apiPost("/dream/start", { motif });
            ctx.ui.notify(`Dream started: ${data.status?.motif ?? motif ?? "auto"}`, "info");
            break;
          }
          case "stop": {
            const data = await apiPost("/dream/stop");
            ctx.ui.notify(
              `Dream stopped: score ${data.best_score} after ${data.iterations} iterations`,
              "info"
            );
            break;
          }
          case "history": {
            const data = await apiGet("/dream/history");
            ctx.ui.notify(`Dream history: ${data.total} total dreams`, "info");
            break;
          }
          case "detail": {
            const id = parts[1];
            if (!id) {
              ctx.ui.notify("Usage: /dream detail <dream_id>", "error");
              return;
            }
            const data = await apiGet(`/dream/${encodeURIComponent(id)}`);
            ctx.ui.notify(`Dream: ${data.dream?.motif ?? "unknown"}`, "info");
            break;
          }
          default:
            ctx.ui.notify("Unknown subcommand. Use: status | start [motif] | stop | history | detail <id>", "error");
        }
      } catch (e: any) {
        ctx.ui.notify(`DreamWeaver error: ${e.message}`, "error");
      }
    },
  });
}
