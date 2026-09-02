import type { MetadataRoute } from "next";

/**
 * Only the surfaces that are meaningful without a session. Public profiles are
 * generated per handle and are discovered through the pages that link to them,
 * so they are not enumerated here.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://devstacks.dev";
  const lastModified = new Date();

  return [
    { url: `${base}/`, lastModified, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/try`, lastModified, changeFrequency: "monthly", priority: 0.7 },
  ];
}
