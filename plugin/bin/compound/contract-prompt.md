# Sprint Contract

You are proposing a sprint contract. This contract defines what you will build
and exactly how the evaluator should verify it.

## Why This Matters

The evaluator is a separate agent that will test your work by navigating the
RUNNING APPLICATION via Playwright. It will not read your code. If you don't
specify exactly what to test and how, the evaluator will miss features or
grade against wrong expectations.

## Contract Format

Output a JSON file:

{
"approved": false,
"version": 1,
"summary": "One-line description of what will be built",
"deliverables": [
{
"description": "What the user can do after this is complete",
"verification": {
"browser": ["Navigate to /page", "Click button", "Fill form", "Verify result"],
"api": ["POST /api/endpoint returns 201"],
"visual": ["Form centered on mobile", "Error states visible"]
}
}
],
"gradingExpectations": {
"design": "What good design means for this feature -- specific, not vague",
"originality": "What distinguishes this from generic AI template output",
"craft": "What polish looks like -- loading states, error handling, transitions",
"functionality": "Every user flow that must work end-to-end"
},
"outOfScope": ["Items the evaluator should NOT test or penalize"]
}

## Rules

1. Every deliverable MUST have browser verification steps the evaluator can follow
2. Visual checks MUST be specific ("button is blue" not "button looks nice")
3. API checks MUST include method, URL, and expected status
4. Grading expectations MUST be concrete for each of the four dimensions
5. Out-of-scope prevents the evaluator from penalizing unrelated areas
