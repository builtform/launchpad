# Rendering Performance — MEDIUM

Optimizing the rendering process reduces the work the browser does.

---

## rendering-animate-svg-wrapper — Animate Wrapper, Not SVG

**Impact: LOW (enables hardware acceleration)**

Many browsers lack hardware acceleration for CSS animations on SVG elements.

**Incorrect:**

```tsx
<svg className="animate-spin" width="24" height="24" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" stroke="currentColor" />
</svg>
```

**Correct:**

```tsx
<div className="animate-spin">
  <svg width="24" height="24" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="10" stroke="currentColor" />
  </svg>
</div>
```

---

## rendering-content-visibility — CSS content-visibility for Long Lists

**Impact: HIGH (faster initial render)**

```css
.message-item {
  content-visibility: auto;
  contain-intrinsic-size: 0 80px;
}
```

For 1000 items, browser skips layout/paint for ~990 off-screen items (10x faster initial render).

---

## rendering-hoist-jsx — Hoist Static JSX Elements

**Impact: LOW (avoids re-creation)**

Extract static JSX outside components.

**Incorrect:**

```tsx
function LoadingSkeleton() {
  return <div className="animate-pulse h-20 bg-gray-200" />;
}
```

**Correct:**

```tsx
const loadingSkeleton = <div className="animate-pulse h-20 bg-gray-200" />;
```

Especially helpful for large static SVG nodes. React Compiler does this automatically if enabled.

---

## rendering-svg-precision — Reduce SVG Coordinate Precision

**Impact: LOW (reduces file size)**

**Incorrect:** `<path d="M 10.293847 20.847362 L 30.938472 40.192837" />`

**Correct:** `<path d="M 10.3 20.8 L 30.9 40.2" />`

Automate: `npx svgo --precision=1 --multipass icon.svg`

---

## rendering-hydration-no-flicker — Prevent Hydration Mismatch Without Flickering

**Impact: MEDIUM (avoids visual flicker and hydration errors)**

For client-only data (localStorage, cookies), inject a synchronous script before React hydrates.

**Incorrect: flickers**

```tsx
function ThemeWrapper({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    const stored = localStorage.getItem("theme");
    if (stored) setTheme(stored);
  }, []);
  return <div className={theme}>{children}</div>;
}
```

**Correct: no flicker**

```tsx
function ThemeWrapper({ children }: { children: ReactNode }) {
  return (
    <>
      <div id="theme-wrapper">{children}</div>
      <script
        dangerouslySetInnerHTML={{
          __html: `
        (function() {
          try {
            var theme = localStorage.getItem('theme') || 'light';
            var el = document.getElementById('theme-wrapper');
            if (el) el.className = theme;
          } catch (e) {}
        })();
      `,
        }}
      />
    </>
  );
}
```

---

## rendering-hydration-suppress-warning — Suppress Expected Mismatches

**Impact: LOW-MEDIUM**

For intentionally different server/client values (dates, random IDs), use `suppressHydrationWarning`.

```tsx
<span suppressHydrationWarning>{new Date().toLocaleString()}</span>
```

Do not use to hide real bugs.

---

## rendering-activity — Use Activity Component for Show/Hide

**Impact: MEDIUM (preserves state/DOM)**

```tsx
import { Activity } from "react";

function Dropdown({ isOpen }: Props) {
  return (
    <Activity mode={isOpen ? "visible" : "hidden"}>
      <ExpensiveMenu />
    </Activity>
  );
}
```

---

## rendering-conditional-render — Use Explicit Conditional Rendering

**Impact: LOW (prevents rendering 0 or NaN)**

**Incorrect: renders "0" when count is 0**

```tsx
{
  count && <span className="badge">{count}</span>;
}
```

**Correct:**

```tsx
{
  count > 0 ? <span className="badge">{count}</span> : null;
}
```

---

## rendering-usetransition-loading — useTransition Over Manual Loading States

**Impact: LOW (reduces re-renders)**

**Incorrect:**

```tsx
const [isLoading, setIsLoading] = useState(false);
const handleSearch = async (value: string) => {
  setIsLoading(true);
  const data = await fetchResults(value);
  setResults(data);
  setIsLoading(false);
};
```

**Correct:**

```tsx
const [isPending, startTransition] = useTransition();
const handleSearch = (value: string) => {
  setQuery(value);
  startTransition(async () => {
    const data = await fetchResults(value);
    setResults(data);
  });
};
```

---

## rendering-resource-hints — React DOM Resource Hints

**Impact: HIGH (reduces load time for critical resources)**

```tsx
import { preconnect, prefetchDNS, preload, preinit } from "react-dom";

export default function App() {
  prefetchDNS("https://analytics.example.com");
  preconnect("https://api.example.com");
  preload("/fonts/inter.woff2", { as: "font", type: "font/woff2", crossOrigin: "anonymous" });
  return <main>{/* content */}</main>;
}
```

| API           | Use case                                    |
| ------------- | ------------------------------------------- |
| `prefetchDNS` | Third-party domains you connect to later    |
| `preconnect`  | APIs/CDNs you fetch from immediately        |
| `preload`     | Critical resources for current page         |
| `preinit`     | Stylesheets/scripts that must execute early |

---

## rendering-script-defer-async — Use defer or async on Script Tags

**Impact: HIGH (eliminates render-blocking)**

In Next.js, use `next/script` with `strategy` prop:

```tsx
import Script from 'next/script'

<Script src="https://example.com/analytics.js" strategy="afterInteractive" />
<Script src="/scripts/utils.js" strategy="beforeInteractive" />
```
