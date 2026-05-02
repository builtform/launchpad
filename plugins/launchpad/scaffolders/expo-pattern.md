---
stack: expo
pillar: Frontend Mobile (RN)
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: npx create-expo-app@latest --yes --template blank-typescript
scaffolder_command_pinned_version: create-expo-app@52
---

# Expo — Knowledge Anchor

## Idiomatic 2026 pattern

Expo SDK 52+ is the canonical React Native development platform for cross-
platform mobile (iOS + Android, with web target via React Native Web). The
2026 idiom uses TypeScript-first, **Expo Router** as the file-based routing
solution (replaces React Navigation as the recommended path for new apps),
**EAS Build** for cloud-based native builds (replaces local Xcode/Android
Studio for most workflows), the **New Architecture** (Fabric + TurboModules)
enabled by default in SDK 52+, and `pnpm`/`bun` as the canonical package
manager.

Canonical layout from `create-expo-app --template blank-typescript`:

```
<app>/
  app/                # Expo Router file-based routes (after `npx expo install
                      # expo-router` if not in template)
    _layout.tsx
    index.tsx
    (tabs)/           # group routes
      _layout.tsx
      home.tsx
  assets/             # images, fonts
  components/
  hooks/
  app.json            # Expo config (name, slug, ios, android, plugins)
  package.json
  tsconfig.json
  babel.config.js     # Expo's Babel preset
  metro.config.js     # Metro bundler config (optional)
  index.ts            # entry point (Expo Router uses `expo-router/entry`)
  .gitignore
```

Version pins:

- `expo@~52.x`
- `react@18.3` (Expo SDK 52 baseline; SDK 53 moves to React 19)
- `react-native@0.76` (Expo SDK 52 baseline)
- `expo-router@~4.x` (matches Expo SDK 52)
- `typescript@~5.3`
- `@types/react@~18.3`
- `eas-cli` (global install; CI installs per-build)

## Scaffolder behavior

`npx create-expo-app@latest --yes --template blank-typescript` runs the
official Expo CLI in non-interactive mode. Available templates: `blank`,
`blank-typescript`, `tabs` (Expo Router with tab nav), `default`. The
scaffolder writes:

- `package.json` with Expo SDK 52 deps pinned
- `tsconfig.json` extending `expo/tsconfig.base`
- `app.json` with default project metadata (slug auto-generated from `<app>`)
- `index.ts` entry point
- `App.tsx` (blank template) OR `app/` directory (tabs template with Expo
  Router)
- `assets/` with default icon + splash
- `babel.config.js`, `.gitignore`, `README.md`

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

- `app.json` at repo root with `"expo": {` block containing `"name"` + `"slug"`
- `package.json` with `expo` in dependencies
- `babel.config.js` with `babel-preset-expo`
- `app/` directory with `_layout.tsx` (Expo Router) OR `App.tsx` at root
  (legacy)
- `eas.json` (EAS Build configured)
- `.expo/` directory (Expo's local cache)

## Common pitfalls + cold-rerun gotchas

- React Native Web target requires `react-native-web` + `react-dom` + Metro
  web config; not in the blank-typescript template by default. Add via `npx
expo install react-dom react-native-web`.
- The New Architecture (Fabric + TurboModules) enabled in SDK 52 breaks some
  legacy native modules; check `expo-doctor` output for incompatible pkgs.
- Expo Router `_layout.tsx` files must export a default React component; missing
  default export fails silently with a route-not-found error.
- `expo install` (NOT `npm install`) is the canonical way to add deps that need
  Expo SDK alignment; using `npm install` directly can install incompatible
  versions of `react-native`/`react`.
- iOS simulator requires macOS + Xcode; Android emulator requires Android
  Studio + SDK + AVD. EAS Build cloud-builds avoid this for production.
- `app.json` `"slug"` field is the unique identifier for EAS; changing it later
  breaks build pipelines.
- Web target uses Metro by default in SDK 52+ (not Webpack); CSS imports work
  but PostCSS chains don't.

## Version evolution

- Expo SDK 52 (2024 H4 → stable 2025): React Native 0.76; New Architecture
  default-on; Metro web bundler default; `expo-image` v2.
- Expo SDK 51 (2024): React Native 0.74; expo-router stable; `expo-asset` v2.
- Expo SDK 50 (2023 H4): React Native 0.73; New Architecture experimental;
  expo-router beta.

Track upstream Expo SDK releases (twice-yearly cadence); SDK upgrades require
running `expo install --fix` to align all SDK-aware deps.
