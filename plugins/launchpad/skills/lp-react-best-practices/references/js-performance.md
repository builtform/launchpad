# JavaScript Performance — LOW-MEDIUM

Micro-optimizations for hot paths that add up to meaningful improvements.

---

## js-batch-dom-css — Avoid Layout Thrashing

**Impact: MEDIUM (prevents forced synchronous layouts)**

Do not interleave style writes with layout reads.

**Incorrect: interleaved reads and writes force reflows**

```typescript
element.style.width = "100px";
const width = element.offsetWidth; // Forces reflow
element.style.height = "200px";
const height = element.offsetHeight; // Forces another reflow
```

**Correct: batch writes, then read**

```typescript
element.style.width = "100px";
element.style.height = "200px";
const { width, height } = element.getBoundingClientRect();
```

**Better: use CSS classes (especially with Tailwind)**

```tsx
<div className={isHighlighted ? "highlighted-box" : ""}>Content</div>
```

---

## js-index-maps — Build Index Maps for Repeated Lookups

**Impact: LOW-MEDIUM (1M ops to 2K ops)**

**Incorrect (O(n) per lookup):**

```typescript
return orders.map((order) => ({
  ...order,
  user: users.find((u) => u.id === order.userId),
}));
```

**Correct (O(1) per lookup):**

```typescript
const userById = new Map(users.map((u) => [u.id, u]));
return orders.map((order) => ({ ...order, user: userById.get(order.userId) }));
```

---

## js-cache-property-access — Cache Properties in Loops

**Impact: LOW-MEDIUM**

**Incorrect:** `for (let i = 0; i < arr.length; i++) { process(obj.config.settings.value) }`

**Correct:**

```typescript
const value = obj.config.settings.value;
const len = arr.length;
for (let i = 0; i < len; i++) {
  process(value);
}
```

---

## js-cache-function-results — Cache Repeated Function Calls

**Impact: MEDIUM**

Use a module-level Map. Works everywhere (utilities, event handlers, not just components).

```typescript
const slugifyCache = new Map<string, string>();
function cachedSlugify(text: string): string {
  if (slugifyCache.has(text)) return slugifyCache.get(text)!;
  const result = slugify(text);
  slugifyCache.set(text, result);
  return result;
}
```

---

## js-cache-storage — Cache Storage API Calls

**Impact: LOW-MEDIUM**

localStorage, sessionStorage, and document.cookie are synchronous and expensive. Cache reads.

```typescript
const storageCache = new Map<string, string | null>();

function getLocalStorage(key: string) {
  if (!storageCache.has(key)) storageCache.set(key, localStorage.getItem(key));
  return storageCache.get(key);
}

function setLocalStorage(key: string, value: string) {
  localStorage.setItem(key, value);
  storageCache.set(key, value);
}
```

Invalidate on external changes:

```typescript
window.addEventListener("storage", (e) => {
  if (e.key) storageCache.delete(e.key);
});
```

---

## js-combine-iterations — Combine Multiple Array Iterations

**Impact: LOW-MEDIUM**

**Incorrect: 3 iterations**

```typescript
const admins = users.filter((u) => u.isAdmin);
const testers = users.filter((u) => u.isTester);
const inactive = users.filter((u) => !u.isActive);
```

**Correct: 1 iteration**

```typescript
const admins: User[] = [],
  testers: User[] = [],
  inactive: User[] = [];
for (const user of users) {
  if (user.isAdmin) admins.push(user);
  if (user.isTester) testers.push(user);
  if (!user.isActive) inactive.push(user);
}
```

---

## js-length-check-first — Early Length Check for Array Comparisons

**Impact: MEDIUM-HIGH**

```typescript
function hasChanges(current: string[], original: string[]) {
  if (current.length !== original.length) return true;
  const currentSorted = current.toSorted();
  const originalSorted = original.toSorted();
  for (let i = 0; i < currentSorted.length; i++) {
    if (currentSorted[i] !== originalSorted[i]) return true;
  }
  return false;
}
```

---

## js-early-exit — Early Return from Functions

**Impact: LOW-MEDIUM**

```typescript
function validateUsers(users: User[]) {
  for (const user of users) {
    if (!user.email) return { valid: false, error: "Email required" };
    if (!user.name) return { valid: false, error: "Name required" };
  }
  return { valid: true };
}
```

---

## js-hoist-regexp — Hoist RegExp Outside Render/Loops

**Impact: LOW-MEDIUM**

**Incorrect:** `const regex = new RegExp(...)` inside render

**Correct:**

```tsx
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function Highlighter({ text, query }: Props) {
  const regex = useMemo(() => new RegExp(`(${escapeRegex(query)})`, 'gi'), [query])
  return <>{text.split(regex).map(...)}</>
}
```

Warning: global regex (`/g`) has mutable `lastIndex` state.

---

## js-min-max-loop — Loop for Min/Max, Not Sort

**Impact: LOW (O(n) vs O(n log n))**

```typescript
function getLatestProject(projects: Project[]) {
  if (projects.length === 0) return null;
  let latest = projects[0];
  for (let i = 1; i < projects.length; i++) {
    if (projects[i].updatedAt > latest.updatedAt) latest = projects[i];
  }
  return latest;
}
```

---

## js-set-map-lookups — Set/Map for O(1) Lookups

**Impact: LOW-MEDIUM**

**Incorrect:** `allowedIds.includes(item.id)`

**Correct:** `new Set(allowedIds).has(item.id)`

---

## js-tosorted-immutable — toSorted() for Immutability

**Impact: MEDIUM-HIGH (prevents mutation bugs in React state)**

**Incorrect:** `users.sort((a, b) => ...)` — mutates original

**Correct:** `users.toSorted((a, b) => ...)` — creates new array

Also: `.toReversed()`, `.toSpliced()`, `.with()`.

---

## js-flatmap-filter — flatMap to Map and Filter in One Pass

**Impact: LOW-MEDIUM**

**Incorrect: 2 iterations**

```typescript
const names = users.map((u) => (u.isActive ? u.name : null)).filter(Boolean);
```

**Correct: 1 iteration**

```typescript
const names = users.flatMap((u) => (u.isActive ? [u.name] : []));
```
