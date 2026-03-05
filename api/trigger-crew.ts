/**
 * Vercel Serverless Function — /api/trigger-crew
 * Called by Vercel Cron every day at 11:00 UTC (6am ET).
 * Forwards the trigger to Railway where the actual crew runs.
 */

import type { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow Vercel Cron (or manual call with secret)
  const auth = req.headers.authorization;
  if (auth !== `Bearer ${process.env.CRON_SECRET}`) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  try {
    const response = await fetch(process.env.RAILWAY_WEBHOOK_URL!, {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization:  `Bearer ${process.env.RAILWAY_SECRET}`,
      },
      body: JSON.stringify({ mode: "all" }),
    });

    if (!response.ok) {
      throw new Error(`Railway returned ${response.status}`);
    }

    // Log to Supabase
    const { createClient } = await import("@supabase/supabase-js");
    const supabase = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_KEY!
    );
    await supabase.from("run_log").insert({
      triggered_at: new Date().toISOString(),
      status:       "triggered",
      source:       "vercel-cron",
    });

    return res.json({ status: "triggered", timestamp: new Date().toISOString() });
  } catch (err: any) {
    console.error("Trigger error:", err);
    return res.status(500).json({ error: err.message });
  }
}
