# Evaluation: react-best-practices

> **Purpose:** Test that the skill produces correct, differentiated output across representative scenarios.
> **Minimum:** 3 scenarios
> **Test with:** Haiku, Sonnet, and Opus to verify model-agnostic behavior

---

## Scenario 1: Happy Path — New Server Component with Data Fetching

**Description:** Tests that the skill applies waterfall elimination, RSC serialization, and Suspense patterns when creating a typical server component page.

**Input:**

```
Create a project dashboard page that shows project details, team members, and recent activity. The page fetches from three independent data sources.
```

**Expected behavior:**

- [ ] Uses parallel data fetching (Promise.all or separate async components), not sequential awaits
- [ ] Wraps slow data sections in Suspense boundaries with skeleton fallbacks
- [ ] Minimizes serialization at RSC boundaries — passes only needed fields to client components
- [ ] Uses React.cache() for any auth/user queries that may be called multiple times
- [ ] Does not use forwardRef; uses use() instead of useContext() (React 19 rules)

**Baseline comparison:** Without this skill, Claude would likely write sequential `await` calls in a single async function, pass full objects to client components, and skip Suspense boundaries.

---

## Scenario 2: Edge Case — Component with Boolean Prop Proliferation

**Description:** Tests that the skill detects boolean prop patterns and recommends composition when refactoring a component with many variant modes.

**Input:**

```
Refactor this component:

function MessageComposer({ isThread, isEditing, isForwarding, isDM, showAttachments, showFormatting }: Props) {
  return (
    <form>
      {isEditing ? <EditHeader /> : <Header />}
      <Input />
      {showAttachments && <Attachments />}
      {isThread && <ThreadOptions />}
      {isDM && <DMOptions />}
      {isEditing ? <EditActions /> : isForwarding ? <ForwardActions /> : <DefaultActions />}
      {showFormatting && <Formatting />}
    </form>
  )
}
```

**Expected behavior:**

- [ ] Flags boolean prop proliferation as a composition-avoid-boolean-props violation
- [ ] Recommends compound component pattern with explicit variants (ThreadComposer, EditComposer, etc.)
- [ ] Shows the context interface pattern (state/actions/meta)
- [ ] Recommends lifting state into providers
- [ ] Each variant explicitly composes only the pieces it needs

**Baseline comparison:** Without this skill, Claude would likely keep the boolean props and just clean up the conditional rendering, possibly adding more booleans.

---

## Scenario 3: Negative Boundary — Backend API Route (Hono)

**Description:** Tests that the skill correctly does NOT activate for Hono API route code that has no React/Next.js involvement.

**Input:**

```
Create a new Hono API route at apps/api/src/routes/projects.ts that lists projects from the database with pagination.
```

**Expected behavior:**

- [ ] Skill does NOT activate — Hono API routes are explicitly out of scope
- [ ] Claude handles the task using standard backend patterns without applying React rules
- [ ] No mention of Suspense, RSC serialization, or component composition

---

## Scenario 4: Happy Path — Performance Optimization of Existing List

**Description:** Tests that the skill applies rendering performance and re-render optimization rules to an existing component.

**Input:**

```
This project list is slow with 500+ items. Optimize it:

function ProjectList({ projects }: { projects: Project[] }) {
  const [filter, setFilter] = useState('')
  const filtered = projects.filter(p => p.name.includes(filter)).sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div>
      <input value={filter} onChange={e => setFilter(e.target.value)} />
      {filtered.map(p => <ProjectCard key={p.id} project={p} />)}
    </div>
  )
}
```

**Expected behavior:**

- [ ] Flags .sort() mutation — recommends .toSorted() (js-tosorted-immutable)
- [ ] Recommends content-visibility: auto for long list items (rendering-content-visibility)
- [ ] Recommends useMemo for the filtered+sorted computation or extraction to a memoized component
- [ ] Recommends startTransition for the filter input (rerender-transitions)
- [ ] Does NOT wrap the simple `p.name.includes(filter)` boolean in useMemo (rerender-simple-expression-in-memo)

**Baseline comparison:** Without this skill, Claude would likely add useMemo around the filter but miss content-visibility, .toSorted(), and startTransition.

---

## Grading

| Scenario | Haiku | Sonnet | Opus |
| -------- | ----- | ------ | ---- |
| 1        |       |        |      |
| 2        |       |        |      |
| 3        |       |        |      |
| 4        |       |        |      |
