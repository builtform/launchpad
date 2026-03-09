# Evaluation Template for Skills

> **Rules for evaluation files:**
>
> 1. Place evaluation files at `.claude/skills/<skill-name>/evals/`
> 2. At least 3 scenarios: happy path, edge case, negative boundary
> 3. Every scenario must include a baseline comparison — what Claude does WITHOUT the skill
> 4. Expected behavior must be specific and observable, not vague
> 5. Test across model tiers (Haiku, Sonnet, Opus) to verify the skill works regardless of model capability
> 6. The grading table tracks pass/fail per model per scenario

---

# Evaluation: {{Skill Name}}

> **Purpose:** Test that the skill produces correct, differentiated output across representative scenarios.
> **Minimum:** 3 scenarios (Anthropic guidance: "at least three evaluations created")
> **Test with:** Haiku, Sonnet, and Opus to verify model-agnostic behavior

---

## Scenario 1: {{Name — e.g., "Happy Path"}}

**Description:** {{What this scenario tests}}

**Input:**

```
{{Exact user input or invocation}}
```

**Expected behavior:**

- [ ] {{Specific observable behavior 1}}
- [ ] {{Specific observable behavior 2}}
- [ ] {{Specific observable behavior 3}}

**Baseline comparison:** Without this skill, Claude would {{describe the generic/inferior behavior}}.

---

## Scenario 2: {{Name — e.g., "Edge Case"}}

**Description:** {{What edge case this tests}}

**Input:**

```
{{Exact user input — intentionally tricky or minimal}}
```

**Expected behavior:**

- [ ] {{How the skill handles the edge case}}
- [ ] {{Graceful degradation or explicit refusal}}

**Baseline comparison:** Without this skill, Claude would {{describe the failure mode}}.

---

## Scenario 3: {{Name — e.g., "Negative Boundary"}}

**Description:** {{Tests that the skill correctly DOES NOT activate for out-of-scope inputs}}

**Input:**

```
{{Input that looks related but is actually out of scope}}
```

**Expected behavior:**

- [ ] Skill does NOT activate
- [ ] Claude handles normally without skill interference

---

## Grading

| Scenario | Haiku | Sonnet | Opus |
| -------- | ----- | ------ | ---- |
| 1        |       |        |      |
| 2        |       |        |      |
| 3        |       |        |      |
