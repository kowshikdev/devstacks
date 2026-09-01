import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Signed-in surfaces carry no public value and require a session anyway.
        disallow: ["/dashboard", "/dashboard/", "/onboarding", "/auth/", "/login"],
      },
    ],
  };
}
