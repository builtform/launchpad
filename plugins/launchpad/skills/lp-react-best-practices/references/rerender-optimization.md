# Re-render Optimization — MEDIUM

Reducing unnecessary re-renders minimizes wasted computation and improves UI responsiveness.

---

## rerender-derived-state-no-effect — Derive State During Render

**Impact: MEDIUM (avoids redundant renders and state drift)**

If a value can be computed from props/state, derive it during render. Do not store in state or update via effect.

**Incorrect:**

```tsx
const [fullName, setFullName] = useState("");
useEffect(() => {
  setFullName(firstName + " " + lastName);
}, [firstName, lastName]);
```

**Correct:**

```tsx
const fullName = firstName + " " + lastName;
```

---

## rerender-defer-reads — Defer State Reads to Usage Point

**Impact: MEDIUM (avoids unnecessary subscriptions)**

Do not subscribe to dynamic state if you only read it inside callbacks.

**Incorrect: subscribes to all searchParams changes**

```tsx
function ShareButton({ chatId }: { chatId: string }) {
  const searchParams = useSearchParams();
  const handleShare = () => {
    const ref = searchParams.get("ref");
    shareChat(chatId, { ref });
  };
  return <button onClick={handleShare}>Share</button>;
}
```

**Correct: reads on demand**

```tsx
function ShareButton({ chatId }: { chatId: string }) {
  const handleShare = () => {
    const params = new URLSearchParams(window.location.search);
    shareChat(chatId, { ref: params.get("ref") });
  };
  return <button onClick={handleShare}>Share</button>;
}
```

---

## rerender-memo — Extract to Memoized Components

**Impact: MEDIUM (enables early returns before computation)**

**Incorrect: computes avatar even when loading**

```tsx
function Profile({ user, loading }: Props) {
  const avatar = useMemo(() => {
    const id = computeAvatarId(user);
    return <Avatar id={id} />;
  }, [user]);
  if (loading) return <Skeleton />;
  return <div>{avatar}</div>;
}
```

**Correct: skips computation when loading**

```tsx
const UserAvatar = memo(function UserAvatar({ user }: { user: User }) {
  const id = useMemo(() => computeAvatarId(user), [user]);
  return <Avatar id={id} />;
});

function Profile({ user, loading }: Props) {
  if (loading) return <Skeleton />;
  return (
    <div>
      <UserAvatar user={user} />
    </div>
  );
}
```

---

## rerender-memo-with-default-value — Hoist Default Non-Primitive Props

**Impact: MEDIUM (restores broken memoization)**

**Incorrect: onClick has different value on every render**

```tsx
const UserAvatar = memo(function UserAvatar({ onClick = () => {} }: Props) { ... })
```

**Correct: stable default**

```tsx
const NOOP = () => {}
const UserAvatar = memo(function UserAvatar({ onClick = NOOP }: Props) { ... })
```

---

## rerender-dependencies — Narrow Effect Dependencies

**Impact: LOW (minimizes effect re-runs)**

Use primitives, not objects.

**Incorrect:** `useEffect(() => { ... }, [user])`

**Correct:** `useEffect(() => { ... }, [user.id])`

For derived state, compute outside the effect:

```tsx
const isMobile = width < 768;
useEffect(() => {
  if (isMobile) enableMobileMode();
}, [isMobile]);
```

---

## rerender-derived-state — Subscribe to Derived Booleans

**Impact: MEDIUM (reduces re-render frequency)**

**Incorrect: re-renders on every pixel**

```tsx
const width = useWindowWidth();
const isMobile = width < 768;
```

**Correct: re-renders only on boolean transition**

```tsx
const isMobile = useMediaQuery("(max-width: 767px)");
```

---

## rerender-functional-setstate — Functional setState Updates

**Impact: MEDIUM (prevents stale closures)**

**Incorrect: requires state as dependency**

```tsx
const addItems = useCallback(
  (newItems: Item[]) => {
    setItems([...items, ...newItems]);
  },
  [items],
);
```

**Correct: stable callback, no stale closures**

```tsx
const addItems = useCallback((newItems: Item[]) => {
  setItems((curr) => [...curr, ...newItems]);
}, []);
```

---

## rerender-lazy-state-init — Lazy State Initialization

**Impact: MEDIUM (wasted computation on every render)**

**Incorrect: runs on every render**

```tsx
const [searchIndex] = useState(buildSearchIndex(items));
```

**Correct: runs only once**

```tsx
const [searchIndex] = useState(() => buildSearchIndex(items));
```

---

## rerender-simple-expression-in-memo — No useMemo for Simple Primitives

**Impact: LOW-MEDIUM**

Do not wrap simple boolean/number/string expressions in useMemo. The hook overhead exceeds the expression cost.

**Incorrect:**

```tsx
const isLoading = useMemo(
  () => user.isLoading || notifications.isLoading,
  [user.isLoading, notifications.isLoading],
);
```

**Correct:**

```tsx
const isLoading = user.isLoading || notifications.isLoading;
```

---

## rerender-move-effect-to-event — Put Interaction Logic in Event Handlers

**Impact: MEDIUM (avoids effect re-runs and duplicate side effects)**

If a side effect is triggered by a specific user action, run it in the event handler.

**Incorrect: event modeled as state + effect**

```tsx
const [submitted, setSubmitted] = useState(false);
useEffect(() => {
  if (submitted) post("/api/register");
}, [submitted, theme]);
```

**Correct:**

```tsx
function handleSubmit() {
  post("/api/register");
  showToast("Registered", theme);
}
```

---

## rerender-transitions — Use startTransition for Non-Urgent Updates

**Impact: MEDIUM (maintains UI responsiveness)**

```tsx
import { startTransition } from "react";

const handler = () => {
  startTransition(() => setScrollY(window.scrollY));
};
```

---

## rerender-use-ref-transient-values — useRef for Transient Values

**Impact: MEDIUM (avoids re-renders on frequent updates)**

Store frequently-changing values (mouse position, intervals) in refs and update DOM directly.

**Incorrect: renders every mouse move**

```tsx
const [lastX, setLastX] = useState(0);
useEffect(() => {
  const onMove = (e: MouseEvent) => setLastX(e.clientX);
  window.addEventListener("mousemove", onMove);
  return () => window.removeEventListener("mousemove", onMove);
}, []);
```

**Correct: no re-renders**

```tsx
const lastXRef = useRef(0);
const dotRef = useRef<HTMLDivElement>(null);
useEffect(() => {
  const onMove = (e: MouseEvent) => {
    lastXRef.current = e.clientX;
    if (dotRef.current) dotRef.current.style.transform = `translateX(${e.clientX}px)`;
  };
  window.addEventListener("mousemove", onMove);
  return () => window.removeEventListener("mousemove", onMove);
}, []);
```

---

## rerender-no-inline-components — Never Define Components Inside Components

**Impact: HIGH (prevents remount on every render)**

**Incorrect: remounts on every render**

```tsx
function UserProfile({ user, theme }) {
  const Avatar = () => (
    <img src={user.avatarUrl} className={theme === "dark" ? "avatar-dark" : "avatar-light"} />
  );
  return (
    <div>
      <Avatar />
    </div>
  );
}
```

**Correct: defined at module level, pass props**

```tsx
function Avatar({ src, theme }: { src: string; theme: string }) {
  return <img src={src} className={theme === "dark" ? "avatar-dark" : "avatar-light"} />;
}

function UserProfile({ user, theme }) {
  return (
    <div>
      <Avatar src={user.avatarUrl} theme={theme} />
    </div>
  );
}
```

**Symptoms of this bug:** input fields lose focus on keystroke, animations restart, effects re-run on parent render, scroll position resets.
