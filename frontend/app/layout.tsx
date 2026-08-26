import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./styles.css";

export const metadata: Metadata = {
  title: "DevStacks",
  description: "Continuously verified developer evidence graph",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}