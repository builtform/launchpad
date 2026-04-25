# Server-Side Performance — HIGH

Optimizing server-side rendering and data fetching eliminates server-side waterfalls and reduces response times.

---

## server-auth-actions — Authenticate Server Actions Like API Routes

**Impact: CRITICAL (prevents unauthorized access)**

Server Actions are public endpoints. Always verify auth inside each action.

**Incorrect: no auth check**

```typescript
"use server";
export async function deleteUser(userId: string) {
  await db.user.delete({ where: { id: userId } });
}
```

**Correct: auth + authorization inside the action**

```typescript
"use server";
import { verifySession } from "@/lib/auth";

export async function deleteUser(userId: string) {
  const session = await verifySession();
  if (!session) throw new Error("Unauthorized");
  if (session.user.role !== "admin" && session.user.id !== userId) {
    throw new Error("Forbidden");
  }
  await db.user.delete({ where: { id: userId } });
}
```

---

## server-cache-react — Per-Request Deduplication with React.cache()

**Impact: MEDIUM (deduplicates within request)**

```typescript
import { cache } from "react";

export const getCurrentUser = cache(async () => {
  const session = await auth();
  if (!session?.user?.id) return null;
  return await db.user.findUnique({ where: { id: session.user.id } });
});
```

Multiple calls within a single request execute the query only once. Use for Prisma queries, auth checks, and heavy computations.

**Avoid inline objects as arguments** — React.cache() uses `Object.is` for cache keys. Inline objects always miss.

---

## server-cache-lru — Cross-Request LRU Caching

**Impact: HIGH (caches across requests)**

React.cache() is per-request only. For cross-request caching, use LRU.

```typescript
import { LRUCache } from "lru-cache";

const cache = new LRUCache<string, any>({ max: 1000, ttl: 5 * 60 * 1000 });

export async function getUser(id: string) {
  const cached = cache.get(id);
  if (cached) return cached;
  const user = await db.user.findUnique({ where: { id } });
  cache.set(id, user);
  return user;
}
```

On Vercel Fluid Compute, LRU is especially effective — multiple concurrent requests share the same instance.

---

## server-dedup-props — Avoid Duplicate Serialization in RSC Props

**Impact: LOW (reduces network payload)**

RSC serialization deduplicates by reference, not value. Do transformations in the client.

**Incorrect: duplicates array**

```tsx
<ClientList usernames={usernames} usernamesOrdered={usernames.toSorted()} />
```

**Correct: transform in client**

```tsx
<ClientList usernames={usernames} />;

// Client component:
const sorted = useMemo(() => [...usernames].sort(), [usernames]);
```

---

## server-hoist-static-io — Hoist Static I/O to Module Level

**Impact: HIGH (avoids repeated file/network I/O per request)**

Module-level code runs once when imported, not on every request. Use for fonts, logos, config files, email templates.

Do NOT use for: assets that vary per request, files that change at runtime, large files, sensitive data.

---

## server-serialization — Minimize Serialization at RSC Boundaries

**Impact: HIGH (reduces data transfer size)**

Only pass fields the client actually uses.

**Incorrect: serializes all 50 fields**

```tsx
async function Page() {
  const user = await fetchUser(); // 50 fields
  return <Profile user={user} />;
}
```

**Correct: serializes only needed fields**

```tsx
async function Page() {
  const user = await fetchUser();
  return <Profile name={user.name} />;
}
```

---

## server-parallel-fetching — Parallel Data Fetching with Component Composition

**Impact: CRITICAL (eliminates server-side waterfalls)**

React Server Components execute sequentially within a tree. Restructure with composition.

**Incorrect: Sidebar waits for Page's fetch**

```tsx
export default async function Page() {
  const header = await fetchHeader();
  return (
    <div>
      <div>{header}</div>
      <Sidebar />
    </div>
  );
}
```

**Correct: both fetch simultaneously**

```tsx
async function Header() {
  const data = await fetchHeader();
  return <div>{data}</div>;
}

export default function Page() {
  return (
    <div>
      <Header />
      <Sidebar />
    </div>
  );
}
```

---

## server-after-nonblocking — Use after() for Non-Blocking Operations

**Impact: MEDIUM (faster response times)**

Use Next.js `after()` to schedule work after the response is sent.

**Incorrect: logging blocks response**

```tsx
export async function POST(request: Request) {
  await updateDatabase(request);
  await logUserAction({ userAgent: request.headers.get("user-agent") });
  return Response.json({ status: "success" });
}
```

**Correct: log after response**

```tsx
import { after } from "next/server";

export async function POST(request: Request) {
  await updateDatabase(request);
  after(async () => {
    const userAgent = (await headers()).get("user-agent") || "unknown";
    logUserAction({ userAgent });
  });
  return Response.json({ status: "success" });
}
```

Use for: analytics, audit logging, notifications, cache invalidation, cleanup.
