# Author handoff: {{unit}}

Date: {{date}}. Unit: {{unit}}. This file: {{handoff_path}}.

## Roles

The user decides reserved questions. The Conductor reviews and answers. You are the Author; the Implementer builds later in a separate session.

## Goal

{{goal}}

## Decided

{{decided}}

## Read first

1. "{{protocol_path}}"
   {{read_first}}

## Task in build order

{{task}}

Write the smallest plan, contracts rather than implementation bodies. Harden with `/lp-harden-plan "{{plan_path}}" --full` and `lp-code-simplicity-reviewer`, following the protocol's round cap. Finish with a simplicity pass and delivery.

## Stop points

{{stop_points}}

## Definition of done

{{done}}

## Standing rules

Work in "{{working_directory}}", starting from {{start_reference}}. Project rules: "{{rules_path}}". Inbox: "{{inbox}}". {{standing_rules}}
Models: {{model_rules}}

## Kickoff prompt

```text
You are the Author for {{unit}}. Work in "{{working_directory}}", starting from {{start_reference}}. Read "{{protocol_path}}" first, then this handoff "{{handoff_path}}", then its Read first list in order.

Authorization: plan, harden and decide each finding yourself within this handoff's scope; questions go to the inbox. The Conductor's mechanical rulings carry the user's authority. Push, PR and merge require the user's own word.

Task in build order: {{task}} Write the smallest plan at "{{plan_path}}". Run /lp-harden-plan "{{plan_path}}" --full, with lp-code-simplicity-reviewer in every round, then the protocol's follow-ups and simplicity pass. Deliver to "{{inbox}}".
Stop points: {{stop_points}} Stops are questions with evidence and a recommendation; checkpoints are scheduled and ask nothing.
Definition of done: {{done}}

Wait for "{{inbox}}/verdict-author-1.md": while [ ! -f "{{inbox}}/verdict-author-1.md" ]; do sleep 60; done; cat "{{inbox}}/verdict-author-1.md". On Claude Code run it as a background command; the host wakes the session on exit and ending the turn after starting it is allowed. On Codex keep this loop in the same turn and never end the turn to wait. CONTINUE folds corrections and delivers again; CLOSE ends the work.
Models: {{model_rules}}
Standing rules: {{standing_rules}} Read "{{rules_path}}". Follow the protocol's authority and atomic-write rules. Report tokens, never stop because of them.
```

## CONTINUE prompt

```text
Continue as the Author for {{unit}} after delivery <n>. Work in "{{working_directory}}" from {{start_reference}}. Re-read "{{protocol_path}}", "{{handoff_path}}", "{{plan_path}}" and every file in "{{inbox}}" in name order. Act on the newest verdict or later ruling; if your newest delivery or blocking stop has no answer, wait for it using the protocol's loop. On Claude Code run waits as background commands; the host wakes the session and ending the turn after starting one is allowed. On Codex wait in the same turn, never ending it to wait. Authorization: plan, harden and decide findings within the handoff's scope. Follow its task, stop points, definition of done, models and standing rules; CLOSE ends the work.
```
