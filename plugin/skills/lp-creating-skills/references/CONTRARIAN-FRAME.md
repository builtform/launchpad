# Contrarian Frame

**Core Principle:** The center is exactly where forgettable lives. Before building a skill, write out the lazy/default version. Name every predictable pattern. Engineer AWAY from each one.

A skill that produces output structurally identical to what Claude generates unprompted is dead weight. It burns tokens, adds latency, and delivers zero differentiation. This document is the process for ensuring that never happens.

---

## 1. The Baseline Detection Process

### 1.1 Write the Generic Version First

Ask: "If I prompted Claude with just the topic name and no skill loaded, what would it produce?"

Write that version out explicitly. Capture 3-5 bullet points across three dimensions:

- **Predictable structure** -- What sections, headings, and ordering would appear? (e.g., "Introduction, Steps, Conclusion," "Pros and Cons," "Best Practices")
- **Predictable vocabulary** -- What words and phrases would repeat? (e.g., "comprehensive," "robust," "leverage," "best practices," "it depends")
- **Predictable assumptions** -- What does the default version assume about the user, the context, and the desired output? (e.g., "user wants a general overview," "more detail is always better," "neutrality is safer than a recommendation")

This is your anti-target. Everything on this list is what the skill must NOT produce.

### 1.2 Name the Predictable Patterns

For each element of the generic version, make the pattern explicit:

| Dimension  | Generic Element                            | Named Pattern                         |
| ---------- | ------------------------------------------ | ------------------------------------- |
| Structure  | Numbered steps                             | "Tutorial walkthrough"                |
| Structure  | Pros and cons list                         | "Balanced analysis theater"           |
| Structure  | Best practices checklist                   | "Compliance checklist"                |
| Vocabulary | "comprehensive," "robust"                  | "Authority signaling filler"          |
| Vocabulary | "leverage," "utilize"                      | "Corporate verb inflation"            |
| Vocabulary | "it depends," "depending on your use case" | "Decision avoidance"                  |
| Assumption | User wants a general overview              | "Lowest common denominator targeting" |
| Assumption | More detail is always better               | "Verbosity as thoroughness"           |
| Assumption | Neutrality is safer than commitment        | "Hedge positioning"                   |

Name them. Named patterns are killable. Unnamed patterns are invisible.

### 1.3 Challenge 2-3 Assumptions

Pick the 2-3 most dangerous assumptions -- the ones most likely to make the skill useless if left unchallenged.

For each one, invert it:

| Dangerous Assumption                  | Inversion                                                                        | Consequence for the Skill                                                     |
| ------------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| "User wants a general overview"       | User wants a specific, actionable output for their exact situation               | The skill must demand context upfront and refuse to produce generic summaries |
| "More detail is always better"        | Excess detail obscures the decision. Brevity is a feature                        | The skill must impose word limits or structural compression                   |
| "Neutrality is safer than commitment" | Uncommitted output forces the user to do the thinking the skill should have done | The skill must make recommendations and state them as defaults                |

Document the challenged assumption and the alternative. These inversions become the skill's design constraints.

### 1.4 Engineer Away

For each predictable pattern identified in 1.2, specify the differentiated alternative. Use this format:

> Instead of [generic pattern], this skill [specific alternative].

Examples:

- Instead of a numbered step-by-step walkthrough, this skill produces a decision tree with branching paths based on the user's constraints.
- Instead of listing pros and cons without a recommendation, this skill states the recommended option first, then lists the conditions under which an alternative would be better.
- Instead of using "comprehensive" and "robust" as qualifiers, this skill uses measurable criteria (e.g., "covers all 4 error categories," "handles inputs up to 10MB").

Every "instead of" statement is a binding constraint on the skill's behavior. If the skill ever produces the left side, it has failed.

---

## 2. Banned Patterns (Anti-Slop Checklist)

Apply this checklist to every skill before shipping. If any pattern appears in the skill's output, rewrite that section.

| Pattern                                   | Why It Fails                                                             | Alternative                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------- |
| "Step 1: Understand the requirements"     | Claude does this automatically. Wastes tokens restating the obvious      | Start with the first non-obvious action                        |
| "Consider the following best practices"   | Hedge language + generic advice = zero commitment                        | "Apply these rules: [specific, numbered]"                      |
| "Ensure quality by reviewing your work"   | Every skill should do this. Saying it adds nothing                       | Specify WHAT to check and HOW to evaluate it                   |
| "Here are some tips and tricks"           | Unstructured, non-prescriptive, filler                                   | Encode tips as mandatory workflow steps                        |
| Pros/cons lists without a recommendation  | Defers the decision to the user                                          | Make the decision. State the recommendation. Explain why       |
| "Depending on your use case..."           | Refuses to commit. Forces the user to decide                             | Define the use cases explicitly. Map each to a specific action |
| "It's important to note that..."          | Filler phrase. Zero information density                                  | Delete the phrase. State the fact directly                     |
| "Let's dive in" / "Let's get started"     | Enthusiasm filler. Zero information density                              | Delete entirely                                                |
| "In this guide, we will..."               | Meta-narration about what the document contains instead of containing it | Delete. Start with the content                                 |
| "Feel free to adjust based on your needs" | Abdication disguised as flexibility                                      | State the default. State the specific conditions for deviation |

---

## 3. The Differentiation Test

After writing skill content, apply this test to every major section:

1. Remove the skill file entirely.
2. Give Claude the same task with no skill loaded.
3. Compare outputs.
4. If the outputs are structurally similar, the section adds no value. Rewrite or delete it.

A skill earns its token cost ONLY when it produces output that Claude cannot produce without it.

Three things that do NOT count as differentiation:

- **Formatting changes.** Wrapping the same content in a different Markdown structure is not a new reasoning process.
- **Vocabulary changes.** Replacing "best practices" with "guidelines" changes nothing about the output's substance.
- **Tone changes.** Making the output sound more confident or more casual does not change what decisions get made.

What DOES count:

- **Different information selected.** The skill causes Claude to surface information it would otherwise omit.
- **Different structure of reasoning.** The skill imposes a decision framework that changes the order and priority of considerations.
- **Different output shape.** The skill produces an artifact (decision tree, matrix, scored rubric) that Claude would not spontaneously generate.

---

## 4. Real Cognition vs. AI Cosplay

Skills encode reasoning frameworks, not personas. The difference:

| AI Cosplay (bad)                  | Real Cognition (good)                                                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Think like an expert copywriter" | "Before writing any headline, list 3 emotional triggers for the target audience. Score each 1-5 on specificity. Use the highest-scoring trigger as the headline's core appeal." |
| "Review carefully for quality"    | "Check every claim against these 4 criteria: [list]. Flag any claim scoring below 3/5 on any criterion."                                                                        |
| "Use best practices"              | "Apply the inverted pyramid: conclusion first, evidence second, context last. If any paragraph reverses this order, restructure it."                                            |
| "Be creative and innovative"      | "Generate 3 alternatives. For each, state what it sacrifices compared to the obvious solution. Pick the alternative with the most acceptable tradeoff."                         |
| "Analyze thoroughly"              | "Score on these 5 dimensions. Any dimension below 3 triggers a mandatory revision. Output the scores before the final version."                                                 |

The left column tells Claude to PRETEND. Claude cannot execute a pretense -- it has no internal model of what "thinking like an expert copywriter" means beyond its training distribution. The right column gives Claude a DECISION FRAMEWORK with explicit inputs, operations, and outputs. Claude can execute a framework.

**The test:** If you remove the persona label and keep only the instructions, does the skill still work? If yes, the persona was decoration. If no, the skill was never a skill -- it was a costume.

---

## 5. Applying the Frame to Skill Construction

When building a new skill, execute these steps in order:

1. **Baseline capture.** Prompt Claude with just the task description and no skill. Save the output.
2. **Pattern inventory.** List every structural, vocabulary, and assumption pattern in the baseline output.
3. **Kill list.** Mark the patterns that must not appear in the skill's output. These are non-negotiable.
4. **Inversion list.** For the 2-3 most dangerous assumptions, write the inverted alternative.
5. **Framework design.** Build the skill's reasoning framework around the inversions, not around the baseline.
6. **Differentiation test.** Run the test from Section 3. If any section fails, rewrite it.
7. **Anti-slop sweep.** Run the checklist from Section 2 against the final skill. Delete or rewrite every match.

Do not skip steps. Do not combine steps. The sequence matters because each step constrains the next.

---

## 6. Common Failure Modes

### The Decoration Trap

Adding Markdown formatting, emoji headers, or structured templates to output that is substantively identical to the baseline. This looks like improvement but changes nothing about the reasoning.

**Fix:** Strip all formatting from both the skill output and the baseline. Compare the plain text. If the content is the same, the skill is decoration.

### The Verbosity Trap

Making the skill produce longer, more detailed output than the baseline and calling that "thoroughness." Length is not value. A 2000-word output that says the same thing as a 500-word baseline is worse -- it costs 4x the tokens for zero additional insight.

**Fix:** Measure information density, not word count. Count the number of distinct, actionable claims in each output. Divide by token count. The skill must have a higher ratio.

### The Confidence Trap

Making the skill sound more authoritative without changing the underlying analysis. Bold claims in the same structure with the same reasoning is still the baseline wearing a suit.

**Fix:** Check whether the skill changes WHAT gets recommended, not just HOW confidently it gets recommended. If the recommendations are the same, the confidence is fake.

### The Kitchen Sink Trap

Cramming every possible consideration into the skill to ensure "completeness." This produces bloated skills that are slow to execute and impossible to maintain.

**Fix:** Every section in a skill must pass the differentiation test independently. If a section does not change Claude's behavior, delete it. A lean skill that changes 3 things beats a bloated skill that changes 3 things and restates 20 defaults.

---

## 7. The One-Line Gut Check

Before shipping any skill, answer this question:

**"What does this skill make Claude do that Claude would not do on its own?"**

If the answer is "nothing" or "the same thing but formatted differently," the skill is not ready. Go back to step 1.
