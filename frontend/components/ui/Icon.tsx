import type { SVGProps } from "react";

export type IconProps = Omit<SVGProps<SVGSVGElement>, "children"> & {
  size?: number;
};

/**
 * One stroke-based icon set so every glyph shares weight, terminals, and
 * optical size. Icons inherit `currentColor` and never carry their own color.
 */
/**
 * Every glyph is built from one factory so the whole set shares stroke weight,
 * terminals, and optical size. Icons inherit `currentColor` and never carry
 * their own color. They are decorative by default; pass `aria-label` to make
 * one exposed to assistive technology.
 */
function make(paths: React.ReactNode) {
  return function DevStacksIcon({ size = 16, ...props }: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden={props["aria-label"] ? undefined : true}
        role={props["aria-label"] ? "img" : undefined}
        focusable="false"
        {...props}
      >
        {paths}
      </svg>
    );
  };
}

export const CheckIcon = make(<path d="M4 12.5 9 17.5 20 6.5" />);
export const CheckCircleIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="m8.5 12 2.5 2.5 4.5-5" />
  </>
);
export const XIcon = make(<path d="M6 6 18 18M18 6 6 18" />);
export const XCircleIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5 14.5 14.5M14.5 9.5 9.5 14.5" />
  </>
);
export const AlertIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.75v5M12 16.25h.01" />
  </>
);
export const InfoIcon = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 16.25v-5M12 7.75h.01" />
  </>
);
export const ChevronDownIcon = make(<path d="m6 9.5 6 6 6-6" />);
export const ChevronRightIcon = make(<path d="m9.5 6 6 6-6 6" />);
export const ChevronLeftIcon = make(<path d="m14.5 6-6 6 6 6" />);
export const ArrowRightIcon = make(<path d="M4 12h16M14 6l6 6-6 6" />);
export const ArrowUpRightIcon = make(<path d="M7 17 17 7M8 7h9v9" />);
export const SearchIcon = make(
  <>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.5 4.5" />
  </>
);
export const MenuIcon = make(<path d="M4 7h16M4 12h16M4 17h16" />);
export const RepoIcon = make(
  <>
    <path d="M5 4.5h11.5a1.5 1.5 0 0 1 1.5 1.5v13H6.5A1.5 1.5 0 0 1 5 17.5Z" />
    <path d="M5 17.5A1.5 1.5 0 0 1 6.5 16H18M8.5 8h5" />
  </>
);
export const CommitIcon = make(
  <>
    <circle cx="12" cy="12" r="3.25" />
    <path d="M3 12h5.75M15.25 12H21" />
  </>
);
export const GraphIcon = make(
  <>
    <circle cx="5.5" cy="12" r="2.5" />
    <circle cx="18" cy="6" r="2.5" />
    <circle cx="18" cy="18" r="2.5" />
    <path d="m8 10.9 7.6-3.6M8 13.1l7.6 3.6" />
  </>
);
export const ShieldIcon = make(
  <>
    <path d="M12 3.5 19 6v6c0 4-3 7-7 8.5C8 19 5 16 5 12V6Z" />
    <path d="m9.25 12 2 2 3.5-4" />
  </>
);
export const LockIcon = make(
  <>
    <rect x="4.75" y="10.5" width="14.5" height="9.5" rx="2" />
    <path d="M8.25 10.5V8a3.75 3.75 0 0 1 7.5 0v2.5" />
  </>
);
export const GlobeIcon = make(
  <>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17M12 3.5c2.2 2.4 3.3 5.3 3.3 8.5S14.2 18.1 12 20.5c-2.2-2.4-3.3-5.3-3.3-8.5S9.8 5.9 12 3.5Z" />
  </>
);
export const ClockIcon = make(
  <>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 1.75" />
  </>
);
export const SyncIcon = make(
  <>
    <path d="M20 12a8 8 0 0 1-13.7 5.6M4 12a8 8 0 0 1 13.7-5.6" />
    <path d="M4 20v-4.5h4.5M20 4v4.5h-4.5" />
  </>
);
export const PlugIcon = make(
  <>
    <path d="M9 3.5v5M15 3.5v5" />
    <path d="M6.5 8.5h11v3a5.5 5.5 0 0 1-11 0Z" />
    <path d="M12 17v3.5" />
  </>
);
export const InboxIcon = make(
  <>
    <path d="M4 13.5 6.2 5.8A2 2 0 0 1 8.1 4.5h7.8a2 2 0 0 1 1.9 1.3L20 13.5" />
    <path d="M4 13.5h4l1.2 2.2h5.6l1.2-2.2h4v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z" />
  </>
);
export const GearIcon = make(
  <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 14a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.2a2 2 0 0 1-4 0v-.1a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 4 14a2 2 0 0 1 0-4h.1a1.6 1.6 0 0 0 1.1-2.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 11 4.4a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7 2 2 0 0 1 0 4h-.2Z" />
  </>
);
export const UserIcon = make(
  <>
    <circle cx="12" cy="8.5" r="3.75" />
    <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
  </>
);
export const UsersIcon = make(
  <>
    <circle cx="9" cy="8.5" r="3.25" />
    <path d="M3.5 19.5a5.5 5.5 0 0 1 11 0" />
    <path d="M16 5.6a3.25 3.25 0 0 1 0 5.8M17.5 14.4a5.5 5.5 0 0 1 3 5.1" />
  </>
);
export const SignOutIcon = make(
  <>
    <path d="M14.5 4.5h3a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-3" />
    <path d="M10 8.5 6.5 12 10 15.5M6.5 12h9" />
  </>
);
export const CopyIcon = make(
  <>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3" />
  </>
);
export const LinkIcon = make(
  <>
    <path d="M10.5 13.5a4 4 0 0 0 5.7 0l2.3-2.3a4 4 0 0 0-5.7-5.7l-1.3 1.3" />
    <path d="M13.5 10.5a4 4 0 0 0-5.7 0l-2.3 2.3a4 4 0 0 0 5.7 5.7l1.3-1.3" />
  </>
);
export const SparkIcon = make(
  <path d="M12 3.5 13.9 9 19.5 11l-5.6 2L12 20.5 10.1 13 4.5 11 10.1 9Z" />
);
export const SunIcon = make(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.5v2.2M12 19.3v2.2M4.2 4.2l1.6 1.6M18.2 18.2l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.2 19.8l1.6-1.6M18.2 5.8l1.6-1.6" />
  </>
);
export const MoonIcon = make(
  <path d="M20 14.2A8.5 8.5 0 0 1 9.8 4a8.5 8.5 0 1 0 10.2 10.2Z" />
);
export const MonitorIcon = make(
  <>
    <rect x="3" y="4.5" width="18" height="12" rx="2" />
    <path d="M8.5 20h7M12 16.5V20" />
  </>
);
export const PencilIcon = make(
  <>
    <path d="M4.5 19.5h4L19 9a2.5 2.5 0 0 0-3.5-3.5L5 16Z" />
    <path d="m14.5 6.5 3 3" />
  </>
);
export const StarIcon = make(
  <path d="m12 4 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7L6.9 19.4l1-5.6-4-3.9 5.6-.8Z" />
);
export const FingerprintIcon = make(
  <>
    <path d="M12 10.5v3.5a7 7 0 0 0 1.2 3.9" />
    <path d="M8.5 8.9a4.5 4.5 0 0 1 7 3.7v1.9M5.5 12a6.5 6.5 0 0 1 2-4.7" />
    <path d="M18.5 12a6.5 6.5 0 0 0-2-4.7M9 19.6A9 9 0 0 1 8 15v-3M20.5 14a9 9 0 0 0-14-8.7" />
  </>
);
export const HistoryIcon = make(
  <>
    <path d="M3.8 12a8.2 8.2 0 1 0 2.6-6" />
    <path d="M3.5 4v4.5H8" />
    <path d="M12 8v4.3l3 1.7" />
  </>
);
export const BellIcon = make(
  <>
    <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5.5 1.5 5.5H5S6.5 14 6.5 10Z" />
    <path d="M10.2 18.5a2 2 0 0 0 3.6 0" />
  </>
);

/** GitHub's own mark, filled — the one place a brand glyph is reproduced verbatim. */
export function GitHubIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      fill="currentColor"
      aria-hidden={props["aria-label"] ? undefined : true}
      focusable="false"
      {...props}
    >
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

/**
 * The DevStacks mark: three stacked plates, the top one verified.
 *
 * Literal to the name, and to the model underneath it — evidence accumulates
 * in layers, and the topmost is the one that passed verification. Drawn in
 * perspective so the silhouette stays distinct at 16px, where a set of flat
 * bars would read as a menu button instead.
 */
export function DevStacksMark({ size = 26, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      width={size}
      height={size}
      fill="none"
      aria-hidden={props["aria-label"] ? undefined : true}
      role={props["aria-label"] ? "img" : undefined}
      focusable="false"
      {...props}
    >
      <path d="M16 4.5 27 10.2 16 15.9 5 10.2Z" fill="var(--ds-brand-400)" />
      <path
        d="M16 18.6 25.4 13.7 27 14.6 16 20.3 5 14.6 6.6 13.7Z"
        fill="var(--fg-default)"
        opacity="0.78"
      />
      <path
        d="M16 23 25.4 18.1 27 19 16 24.7 5 19 6.6 18.1Z"
        fill="var(--fg-default)"
        opacity="0.5"
      />
    </svg>
  );
}
