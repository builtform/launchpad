# Profile Template

> **Profiles encode REAL COGNITION, not AI cosplay.**
>
> - "Real cognition" = executable decision frameworks with specific evaluation criteria
> - "AI cosplay" = telling Claude to "think like an expert" (pattern-matches to what sounds expert-like but produces generic output)
>
> Profiles are shared resources — any skill can reference them during its verification gate.
> Build profiles from observed expert behavior, not from stereotypes about what experts do.

---

# Profile: {{Expert Role / Decision Framework Name}}

> **Purpose:** {{What decisions this profile helps make}}
> **Used by:** {{Which skills reference this profile during verification}}

---

## Decision Framework

<!-- What mental model does this expert apply? Not "what would they say"
     but "what sequence of evaluations do they perform?" -->

1. {{First thing they evaluate — the entry point of their reasoning}}
2. {{Second evaluation — what the first result leads them to check}}
3. {{Third evaluation}}

---

## Prioritization Logic

<!-- What do they look at FIRST? What do they consider most important? -->

**Always check first:**

- {{Highest-priority concern}}
- {{Second-priority concern}}

**Defer until later:**

- {{Things they intentionally deprioritize}}

---

## Red Flags

<!-- What makes them immediately suspicious? Specific patterns, not vague concerns. -->

- {{Specific observable pattern}} → {{What it usually indicates}}
- {{Another pattern}} → {{What it indicates}}

---

## Questions Before Judgment

<!-- The specific sequence of questions they ask before committing to a conclusion. -->

1. {{Question 1 — the diagnostic entry point}}
2. {{Question 2 — narrowing down}}
3. {{Question 3 — confirmation}}
4. {{Question 4 — edge case check}}

---

## Deliberately Ignored

<!-- What everyone else obsesses over that this expert consistently ignores.
     This is where the contrarian value lives. -->

- {{Thing others prioritize that this expert deprioritizes — with reason}}
- {{Another}}

---

## Anti-Patterns

| AI Cosplay (bad)                    | Real Cognition (good)                                                                                                                 |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| "Think like a senior engineer"      | "Check: (1) Does every function have a single responsibility? (2) Are all side effects explicit? (3) Is the error path tested?"       |
| "Review as a security expert would" | "Scan for: (1) User input reaching SQL without parameterization (2) Secrets in source (3) Auth bypass via direct object reference"    |
| "Apply UX best practices"           | "For each interaction: (1) Can the user undo it? (2) Is the next action obvious? (3) Does the error message tell them how to fix it?" |

---

Profiles are built once and reused across every skill. They become permanent review infrastructure that compounds over time. Build them from real observed behavior, not from assumptions about what experts do.
