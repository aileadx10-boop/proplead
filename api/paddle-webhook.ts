/**
 * Vercel Serverless Function — /api/paddle-webhook
 * Receives Paddle payment events and provisions/cancels subscribers.
 *
 * Events handled:
 *   subscription.activated → add subscriber to Supabase
 *   subscription.canceled  → deactivate subscriber
 */

import type { NextApiRequest, NextApiResponse } from "next";
import { createClient } from "@supabase/supabase-js";
import crypto from "crypto";

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

function verifySignature(body: string, sig: string): boolean {
  const secret = process.env.PADDLE_WEBHOOK_SECRET!;
  const hmac   = crypto.createHmac("sha256", secret);
  hmac.update(body);
  return hmac.digest("hex") === sig;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== "POST") return res.status(405).end();

  const sig = req.headers["paddle-signature"] as string;
  if (!verifySignature(JSON.stringify(req.body), sig)) {
    return res.status(401).json({ error: "Invalid signature" });
  }

  const { event_type, data } = req.body;

  // ── NEW SUBSCRIBER ──────────────────────────────────────
  if (event_type === "subscription.activated") {
    const { customer_email, custom_data, subscription_id } = data;
    const { name, state, zip } = custom_data || {};

    await supabase.from("subscribers").upsert({
      email:                   customer_email,
      name:                    name || customer_email,
      state:                   state || "TX",
      zip:                     zip   || "00000",
      paddle_subscription_id:  subscription_id,
      active:                  true,
      created_at:              new Date().toISOString(),
    });

    // Increment ZIP slot counter
    await supabase.rpc("increment_zip_used", { p_zip: zip || "00000" });

    // Notify the Railway crew to send a welcome email
    await fetch(process.env.RAILWAY_WEBHOOK_URL!, {
      method:  "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization:  `Bearer ${process.env.RAILWAY_SECRET}`,
      },
      body: JSON.stringify({
        mode: "zip", state: state || "TX", zip: zip || "00000",
      }),
    }).catch(console.error);

    console.log(`✅ Provisioned: ${customer_email}`);
    return res.json({ status: "provisioned" });
  }

  // ── CANCELLATION ───────────────────────────────────────
  if (
    event_type === "subscription.canceled" ||
    event_type === "subscription.paused"
  ) {
    const { subscription_id } = data;

    const { data: sub } = await supabase
      .from("subscribers")
      .select("zip")
      .eq("paddle_subscription_id", subscription_id)
      .single();

    await supabase
      .from("subscribers")
      .update({ active: false, cancelled_at: new Date().toISOString() })
      .eq("paddle_subscription_id", subscription_id);

    if (sub?.zip) {
      await supabase.rpc("decrement_zip_used", { p_zip: sub.zip });
    }

    console.log(`❌ Deactivated: ${subscription_id}`);
    return res.json({ status: "deactivated" });
  }

  return res.json({ status: "ignored", event: event_type });
}
