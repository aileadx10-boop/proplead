/**
 * Vercel Serverless Function — /api/zip-check?zip=78701
 * Called by the landing page to show live slot availability.
 * Example response: { "label": "3 of 5 available", "is_full": false }
 */

import type { NextApiRequest, NextApiResponse } from "next";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const zip = req.query.zip as string;
  if (!zip) return res.status(400).json({ error: "zip required" });

  // Cache response for 60 seconds
  res.setHeader("Cache-Control", "s-maxage=60");

  const { data } = await supabase
    .from("zip_slots")
    .select("used, max")
    .eq("zip", zip)
    .single();

  if (!data) {
    return res.json({ zip, used: 0, max: 5, available: 5,
                      is_full: false, label: "5 of 5 available" });
  }

  const available = Math.max(0, data.max - data.used);
  return res.json({
    zip,
    used:      data.used,
    max:       data.max,
    available,
    is_full:   data.used >= data.max,
    label:     `${available} of ${data.max} available`,
  });
}
