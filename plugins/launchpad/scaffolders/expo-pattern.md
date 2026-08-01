---
stack: expo
pillar: Frontend Mobile (RN)
type: orchestrate
last_validated: 2026-08-01
scaffolder_command: npx create-expo-app@latest --yes --no-agents-md --template default@sdk-57
scaffolder_command_pinned_version: create-expo-app@4.0.0 (Expo SDK 57)
---

# Expo — Knowledge Anchor

## Idiomatic 2026 pattern

Expo SDK 57 is the canonical React Native development platform for cross-
platform mobile (iOS + Android, with web target via React Native Web). The
2026 idiom uses TypeScript-first, **Expo Router** as the file-based routing
solution (replaces React Navigation as the recommended path for new apps),
**EAS Build** for cloud-based native builds (replaces local Xcode/Android
Studio for most workflows), and the **New Architecture** (Fabric +
TurboModules), which since SDK 55 is the ONLY architecture: it is always on and
cannot be disabled. Package manager is a project choice (LaunchPad prefers
`pnpm`); Expo itself supports npm, yarn, pnpm, and bun equally.

Canonical layout from `create-expo-app --template default@sdk-57`:

```
<app>/
  src/
    app/              # Expo Router file-based routes
      _layout.tsx
      index.tsx
      (tabs)/         # group routes
        _layout.tsx
        index.tsx
    components/
    constants/
    hooks/
    global.css        # web/Metro CSS entry
  assets/             # images, fonts
  scripts/
    reset-project.js  # strips the example app
  .vscode/
  app.json            # Expo config (name, slug, ios, android, plugins)
  package.json        # entry is "main": "expo-router/entry" (no index.ts/App.tsx)
  tsconfig.json
  .gitignore
  # NOTE: no babel.config.js and no metro.config.js are generated. Add them only
  # when you need custom config.
```

Version pins:

- `expo@~57.0.x`
- `react@19.2.x` (Expo SDK 57 baseline; use Expo's pin, not npm latest)
- `react-native@0.86.x` (Expo SDK 57 baseline)
- `expo-router@~57.0.x`
- `react-native-web@~0.21.x`, `react-dom@19.2.x` (both in the default template)
- `typescript@~6.0.x` (Expo's pin; TypeScript 7.0 is GA but Expo templates have
  not adopted it, so do not jump ahead of `expo install`)
- `@types/react@~19.2.x`
- `eas-cli` (global install; CI installs per-build)

Since SDK 55, every Expo SDK package shares the SDK major: an SDK 57 project
uses `expo-camera@~57.x`, `expo-image@~57.x`, and so on. Never reason about Expo
package versions using pre-SDK-55 semver families such as `expo-router@4.x`.

## Scaffolder behavior

`npx create-expo-app@latest --yes --no-agents-md --template default@sdk-57`
runs the official Expo CLI in non-interactive mode. Available templates:
`default` (Expo Router + TypeScript + Expo UI; the recommended one), `blank`,
`blank-typescript`, `tabs`, `bare-minimum` (runs prebuild, ships native dirs).
Templates can be SDK-pinned with `@sdk-NN`. The scaffolder writes:

- `package.json` with Expo SDK 57 deps pinned (`"main": "expo-router/entry"`
  for the default/tabs templates)
- `tsconfig.json` extending `expo/tsconfig.base`
- `app.json` with default project metadata (slug auto-generated from `<app>`)
- `src/app/` route tree (default/tabs) OR `App.tsx` + `index.ts` (blank,
  blank-typescript)
- `assets/` with default icon + splash
- `scripts/reset-project.js`, `.vscode/`, `.gitignore`, `README.md`
- `AGENTS.md`, `CLAUDE.md` and `.claude/settings.json` with Expo-specific agent
  guidance (SDK 56+). LaunchPad passes `--no-agents-md` to suppress these so
  they do not collide with the harness-authored `CLAUDE.md`.
- It does NOT write `babel.config.js` or `metro.config.js`. Expo Router's
  install guide now says to delete `babel.config.js` if it holds nothing but
  `babel-preset-expo`.

It DOES install dependencies by default (npm); `--yes` accepts that. To skip
install: `--no-install` flag. LaunchPad uses the default install behavior since
Expo's dep resolution is sensitive to peer-dep alignment (better to let the
CLI manage initial install).

For Expo Router from a blank template: `npx expo install expo-router
react-native-safe-area-context react-native-screens` and convert `App.tsx` to
`app/_layout.tsx` + `app/index.tsx`.

EAS setup (post-scaffold): `eas init` creates `eas.json` with build profiles
(`development`, `preview`, `production`); requires `expo login` first.

## Tier-1 detection signals

- `package.json` with `expo` in dependencies (strongest single signal)
- `app.json` / `app.config.ts` / `app.config.js` at repo root with an `expo`
  config block containing `"name"` + `"slug"`
- `package.json` with `"main": "expo-router/entry"` (Expo Router project)
- `src/app/` OR `app/` directory with `_layout.tsx` (Expo Router) OR `App.tsx`
  at root (blank template)
- `eas.json` (EAS Build configured)
- `.expo/` directory (Expo's local cache)
- WEAK/LEGACY: `babel.config.js` with `babel-preset-expo`. No longer generated
  by any current template, so its absence does NOT rule out Expo.

## Common pitfalls + cold-rerun gotchas

- React Native Web target requires `react-native-web` + `react-dom` + Metro
  web config; not in the blank-typescript template by default. Add via `npx
expo install react-dom react-native-web`.
- The New Architecture (Fabric + TurboModules) is the ONLY architecture from SDK
  55 onward; the legacy architecture was removed and `newArchEnabled` in app
  config is ignored. Native modules that never migrated simply do not work;
  check `npx expo-doctor` before committing to a dependency.
- Expo Router `_layout.tsx` files must export a default React component; missing
  default export fails silently with a route-not-found error.
- `expo install` (NOT `npm install`) is the canonical way to add deps that need
  Expo SDK alignment; using `npm install` directly can install incompatible
  versions of `react-native`/`react`.
- iOS simulator requires macOS + Xcode; Android emulator requires Android
  Studio + SDK + AVD. EAS Build cloud-builds avoid this for production.
- `app.json` `"slug"` field is the unique identifier for EAS; changing it later
  breaks build pipelines.
- Web target uses Metro (Webpack support was deprecated in SDK 50 and is gone).
  Metro web has built-in support for CSS, CSS Modules, Sass, PostCSS and
  Tailwind; a `postcss.config.js` at the project root IS honored.
- `create-expo-app` writes `AGENTS.md`, `CLAUDE.md`, and `.claude/settings.json`
  by default since SDK 56. Pass `--no-agents-md` so they do not collide with
  harness-authored files.
- Expo Go on the App Store / Play Store now lags the newest SDK by design. Plan
  on a development build (`expo-dev-client`) or `eas go` rather than Expo Go.

## Version evolution

- Expo SDK 57 (2026-06-30): React Native 0.86; React 19.2; `expo prebuild` now
  clears and regenerates `android/`+`ios/` by default (pass `--no-clean`).
- Expo SDK 56 (2026-05-21): React Native 0.85; Hermes V1 default; default
  template gains Expo UI; new projects emit `AGENTS.md`/`CLAUDE.md`.
- Expo SDK 55 (2026-02-25): React Native 0.83; **legacy architecture removed**;
  **all SDK packages adopt the SDK major as their own major**; `eas update`
  requires `--environment`.
- Expo SDK 54 (2025): last release supporting the legacy architecture.
- Expo SDK 52 (2024 H4): React Native 0.76; New Architecture default-on; Metro
  web bundler default.

Track upstream Expo SDK releases. The cadence is NOT twice-yearly: Expo shipped
SDK 55, 56 and 57 within H1 2026 and stated with SDK 57 that it intends to track
React Native's six-releases-per-year schedule. Re-validate this anchor at least
quarterly. SDK upgrades require `npx expo install expo@latest --fix` to align
all SDK-aware deps, then `npx expo-doctor`.
