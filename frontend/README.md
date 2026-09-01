# DevStacks Frontend

The DevStacks product surface: a Next.js App Router application with its own
design system, component library, and app chrome.

## Running it

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm run typecheck  # tsc --noEmit
```

Environment variables live in `.env.local` (see `.env.example`). No secret
belongs in a `NEXT_PUBLIC_` variable.

## Architecture

```
app/                     Routes. One file per surface, nothing shared here.
components/
  ui/                    Design-system primitives (the only place new visual
                         vocabulary is introduced).
  AppShell.tsx           Signed-in frame and public frame.
  SiteHeader.tsx         Global header, nav, account menu, mobile drawer.
  SiteFooter.tsx         Global footer.
  CommandPalette.tsx     ⌘K / Ctrl-K navigation and handle lookup.
  ThemeProvider.tsx      Theme preference, persisted, applied before paint.
lib/
  api/client.ts          Typed API client (bearer token from Supabase).
  supabase/client.ts     Auth only.
  hooks/useProfile.ts    Own-profile loading plus auth routing.
  format/time.ts         Pure formatters usable from server components.
styles/
  tokens.css             Primitives, then semantic roles. Themes redefine
                         only the semantic layer.
  base.css               Reset, typography defaults, focus, scrollbars.
  components.css         Component classes (buttons, cards, labels, …).
  layout.css             Chrome and page-level composition.
  utilities.css          Small single-purpose helpers.
```

`app/globals.css` imports the five stylesheets in that order; nothing else
imports CSS directly.

## Design system rules

**Tokens, not values.** Components reference semantic tokens (`--fg-muted`,
`--canvas-subtle`, `--accent-emphasis`), never a raw hex or a primitive
(`--ds-gray-500`). A theme is then a redefinition of the semantic layer alone,
which is why light and dark need no component changes.

**Themes.** Light is the base. `:root[data-theme="dark"]` and the
`prefers-color-scheme` block both define the same dark roles, so an explicit
choice wins in either direction and the system default still works. The
preference is applied by an inline script before first paint — there is no
flash on load.

**One icon set.** `components/ui/Icon.tsx` builds every glyph from one factory,
so stroke weight and optical size stay consistent. Icons are decorative by
default; pass `aria-label` to expose one.

**Accessibility is not a pass at the end.** Every surface has a skip link,
visible focus rings via `:focus-visible`, labelled form controls with
`aria-describedby` wired to hints and errors, a focus-trapping dialog that
restores focus on close, `aria-current` on active navigation, and live regions
for toasts. `prefers-reduced-motion` disables animation.

**States are designed, not assumed.** Each data surface renders four states:
loading (skeletons shaped like the content), empty (with the action that
resolves it), error (with what failed and what to do), and loaded.

## Keyboard

| Where       | Keys                          | Action                       |
| ----------- | ----------------------------- | ---------------------------- |
| Anywhere    | `⌘K` / `Ctrl-K`               | Command palette              |
| Palette     | `↑` `↓` `↵` `esc`             | Navigate, select, close      |
| Review      | `j` `k`                       | Move through the queue       |
| Review      | `a` `r` `e` `p`               | Approve, reject, edit, publish |

Review shortcuts are ignored while a field or dialog has focus.

## Adding a surface

1. Add the route under `app/`.
2. Compose it from `components/ui` — if a primitive is missing, add it there
   rather than styling inline, so it lands in both themes at once.
3. Wrap it in `AppShell` (signed-in) or `PublicShell` (public).
4. Handle all four data states before shipping.
