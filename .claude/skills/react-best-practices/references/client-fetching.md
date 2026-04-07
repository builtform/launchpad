# Client-Side Data Fetching — MEDIUM-HIGH

Automatic deduplication and efficient data fetching patterns reduce redundant network requests.

---

## client-swr-dedup — Use SWR for Automatic Deduplication

**Impact: MEDIUM-HIGH (automatic deduplication)**

**Incorrect: no deduplication, each instance fetches**

```tsx
function UserList() {
  const [users, setUsers] = useState([]);
  useEffect(() => {
    fetch("/api/users")
      .then((r) => r.json())
      .then(setUsers);
  }, []);
}
```

**Correct: multiple instances share one request**

```tsx
import useSWR from "swr";

function UserList() {
  const { data: users } = useSWR("/api/users", fetcher);
}
```

For immutable data use `useSWR` with `{ revalidateOnFocus: false, revalidateOnReconnect: false }`. For mutations use `useSWRMutation`.

---

## client-event-listeners — Deduplicate Global Event Listeners

**Impact: LOW (single listener for N components)**

Use `useSWRSubscription()` or module-level Maps to share global event listeners.

**Incorrect: N instances = N listeners**

```tsx
function useKeyboardShortcut(key: string, callback: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey && e.key === key) callback();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [key, callback]);
}
```

**Correct: module-level Map + single SWR subscription**

```tsx
import useSWRSubscription from "swr/subscription";

const keyCallbacks = new Map<string, Set<() => void>>();

function useKeyboardShortcut(key: string, callback: () => void) {
  useEffect(() => {
    if (!keyCallbacks.has(key)) keyCallbacks.set(key, new Set());
    keyCallbacks.get(key)!.add(callback);
    return () => {
      const set = keyCallbacks.get(key);
      if (set) {
        set.delete(callback);
        if (set.size === 0) keyCallbacks.delete(key);
      }
    };
  }, [key, callback]);

  useSWRSubscription("global-keydown", () => {
    const handler = (e: KeyboardEvent) => {
      if (e.metaKey && keyCallbacks.has(e.key)) {
        keyCallbacks.get(e.key)!.forEach((cb) => cb());
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });
}
```

---

## client-passive-event-listeners — Use Passive Event Listeners

**Impact: MEDIUM (eliminates scroll delay)**

Add `{ passive: true }` to touch and wheel listeners to enable immediate scrolling.

**Incorrect:**

```typescript
document.addEventListener("touchstart", handleTouch);
document.addEventListener("wheel", handleWheel);
```

**Correct:**

```typescript
document.addEventListener("touchstart", handleTouch, { passive: true });
document.addEventListener("wheel", handleWheel, { passive: true });
```

Use passive when: tracking/analytics, logging, any listener that does not call `preventDefault()`.
Do not use passive when: custom swipe gestures, custom zoom controls.

---

## client-localstorage-schema — Version and Minimize localStorage Data

**Impact: MEDIUM (prevents schema conflicts, reduces storage size)**

Add version prefix to keys. Store only needed fields. Always wrap in try-catch.

**Incorrect:**

```typescript
localStorage.setItem("userConfig", JSON.stringify(fullUserObject));
```

**Correct:**

```typescript
const VERSION = "v2";

function saveConfig(config: { theme: string; language: string }) {
  try {
    localStorage.setItem(`userConfig:${VERSION}`, JSON.stringify(config));
  } catch {
    // Throws in incognito, quota exceeded, or disabled
  }
}

function loadConfig() {
  try {
    const data = localStorage.getItem(`userConfig:${VERSION}`);
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}
```
