import Link from "next/link";

import { DevStacksMark, GitHubIcon } from "./ui/Icon";

const COLUMNS: { heading: string; links: { href: string; label: string; external?: boolean }[] }[] = [
  {
    heading: "Product",
    links: [
      { href: "/try", label: "Live preview" },
      { href: "/#how-it-works", label: "How it works" },
      { href: "/#assurance", label: "Assurance model" },
      { href: "/dashboard", label: "Dashboard" },
    ],
  },
  {
    heading: "Connectors",
    links: [
      { href: "/dashboard/connections", label: "GitHub" },
      { href: "/dashboard/connections", label: "LinkedIn export" },
      { href: "/dashboard/connections", label: "HackerRank" },
      { href: "/dashboard/connections", label: "LeetCode" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { href: "/#faq", label: "FAQ" },
      { href: "https://github.com/kowshikdev/devstacks", label: "Source", external: true },
      {
        href: "https://github.com/kowshikdev/devstacks/blob/main/Requirements.md",
        label: "Requirements",
        external: true,
      },
      {
        href: "https://github.com/kowshikdev/devstacks/blob/main/ROADMAP.md",
        label: "Roadmap",
        external: true,
      },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer__grid">
          <div>
            <Link href="/" className="wordmark">
              <DevStacksMark className="wordmark__mark" />
              DevStacks
            </Link>
            <p className="text-sm text-muted mt-3" style={{ maxWidth: "34ch" }}>
              A continuously verified developer evidence graph. Every published claim traces back to
              an immutable observation with recorded provenance.
            </p>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.heading}>
              <p className="footer__heading">{column.heading}</p>
              {column.links.map((link) => (
                <Link
                  key={`${column.heading}-${link.label}`}
                  href={link.href}
                  className="footer__link"
                  {...(link.external ? { target: "_blank", rel: "noreferrer" } : {})}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>

        <div className="footer__bottom">
          <span>© {new Date().getFullYear()} DevStacks. Evidence over assertion.</span>
          <a
            className="row gap-2 text-subtle"
            href="https://github.com/kowshikdev/devstacks"
            target="_blank"
            rel="noreferrer"
          >
            <GitHubIcon size={14} />
            kowshikdev/devstacks
          </a>
        </div>
      </div>
    </footer>
  );
}
