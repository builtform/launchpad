# Bundle Size Optimization — CRITICAL

Reducing initial bundle size improves Time to Interactive and Largest Contentful Paint.

---

## bundle-barrel-imports — Avoid Barrel File Imports

**Impact: CRITICAL (200-800ms import cost)**

Import directly from source files. Barrel files load thousands of unused modules.

**Incorrect: imports entire library**

```tsx
import { Check, X, Menu } from "lucide-react";
// Loads 1,583 modules, 200-800ms on every cold start

import { Button, TextField } from "@mui/material";
// Loads 2,225 modules
```

**Correct: direct imports**

```tsx
import Check from "lucide-react/dist/esm/icons/check";
import X from "lucide-react/dist/esm/icons/x";
import Menu from "lucide-react/dist/esm/icons/menu";
```

**Alternative: Next.js optimizePackageImports**

```js
// next.config.js
module.exports = {
  experimental: {
    optimizePackageImports: ["lucide-react", "@mui/material"],
  },
};
```

Commonly affected: `lucide-react`, `@mui/material`, `@tabler/icons-react`, `react-icons`, `@radix-ui/react-*`, `lodash`, `date-fns`.

---

## bundle-dynamic-imports — Dynamic Imports for Heavy Components

**Impact: CRITICAL (directly affects TTI and LCP)**

Use `next/dynamic` to lazy-load large components not needed on initial render.

**Incorrect: Monaco bundles with main chunk ~300KB**

```tsx
import { MonacoEditor } from "./monaco-editor";
```

**Correct: Monaco loads on demand**

```tsx
import dynamic from "next/dynamic";

const MonacoEditor = dynamic(() => import("./monaco-editor").then((m) => m.MonacoEditor), {
  ssr: false,
});
```

---

## bundle-defer-third-party — Defer Non-Critical Libraries

**Impact: MEDIUM (loads after hydration)**

Analytics, logging, and error tracking do not block user interaction.

**Incorrect: blocks initial bundle**

```tsx
import { Analytics } from "@vercel/analytics/react";
```

**Correct: loads after hydration**

```tsx
import dynamic from "next/dynamic";

const Analytics = dynamic(() => import("@vercel/analytics/react").then((m) => m.Analytics), {
  ssr: false,
});
```

---

## bundle-conditional — Conditional Module Loading

**Impact: HIGH (loads large data only when needed)**

Load large data or modules only when a feature is activated.

```tsx
function AnimationPlayer({ enabled, setEnabled }: Props) {
  const [frames, setFrames] = useState<Frame[] | null>(null);

  useEffect(() => {
    if (enabled && !frames && typeof window !== "undefined") {
      import("./animation-frames.js")
        .then((mod) => setFrames(mod.frames))
        .catch(() => setEnabled(false));
    }
  }, [enabled, frames, setEnabled]);

  if (!frames) return <Skeleton />;
  return <Canvas frames={frames} />;
}
```

---

## bundle-preload — Preload Based on User Intent

**Impact: MEDIUM (reduces perceived latency)**

Preload heavy bundles on hover/focus before they are needed.

```tsx
function EditorButton({ onClick }: { onClick: () => void }) {
  const preload = () => {
    if (typeof window !== "undefined") {
      void import("./monaco-editor");
    }
  };

  return (
    <button onMouseEnter={preload} onFocus={preload} onClick={onClick}>
      Open Editor
    </button>
  );
}
```
