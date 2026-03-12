import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { cors } from "hono/cors";

const app = new Hono();

app.use("/*", cors());

app.get("/health", (c) => {
  return c.json({ status: "ok", timestamp: new Date().toISOString() });
});

const port = Number(process.env.PORT) || 3001;

const startServer = (attemptPort: number, retries = 3) => {
  const server = serve({ fetch: app.fetch, port: attemptPort }, (info) => {
    console.log(`API server running on http://localhost:${info.port}`);
  });

  server.on("error", (err: NodeJS.ErrnoException) => {
    if (err.code === "EADDRINUSE" && retries > 0) {
      const nextPort = attemptPort + 1;
      console.warn(`Port ${attemptPort} in use, trying ${nextPort}...`);
      startServer(nextPort, retries - 1);
    } else {
      console.error(`Failed to start server: ${err.message}`);
      process.exit(1);
    }
  });
};

startServer(port);

export default app;
