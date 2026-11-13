# Implementer handoff: {{unit}}

Date: {{date}}. Unit: {{unit}}. This file: {{handoff_path}}.

## Preconditions

{{preconditions}}

## Roles and models

The user decides reserved questions. The Conductor verifies checkpoints and answers stops. You implement. Models: {{model_rules}}

## Read first

1. "{{protocol_path}}"
   {{read_first}}

## Sections

| Section      | Plan phase | Commit title |
| ------------ | ---------- | ------------ |
| {{sections}} |

PAUSE after every {{pause_every}} sections. The last section is Review: `/lp-review`, all findings fixed or recorded with a reason, gates green, final checkpoint and its verdict, then the push stop.

## Section 1 start

Work in "{{working_directory}}" on {{branch}}, base head {{base_head}}. {{start_steps}}

## Stop points

{{stop_points}}

## Definition of done

{{done}}

## Standing rules

Project rules: "{{rules_path}}". Plan: "{{plan_path}}". Inbox: "{{inbox}}". {{standing_rules}}

## Kickoff prompt

```text
You are the Implementer for {{unit}}. Work in "{{working_directory}}" on {{branch}}, base head {{base_head}}. Read "{{protocol_path}}" first, then this handoff "{{handoff_path}}", then its Read first list in order.

Authorization: implement every section in the handoff's Sections table, one at a time, including staging files by name and committing each section. Each section after the first starts only on a Conductor CONTINUE verdict. Its mechanical rulings carry the user's authority. Push, PR and merge need the user's own word, never a verdict or ruling.

Task in build order: section 1 now, then each next section on CONTINUE. {{start_steps}} The last section runs /lp-review on the whole branch with native LaunchPad review subagents after implementation, fixes every finding or records it with a reason, gets gates green, writes the checkpoint, waits for its verdict and ends at the push stop.
Stop points: {{stop_points}} Stops are questions with evidence and a recommendation; checkpoints are scheduled and ask nothing.
Definition of done: {{done}}

After checkpoint 1 wait for "{{inbox}}/verdict-implementer-1.md": while [ ! -f "{{inbox}}/verdict-implementer-1.md" ]; do sleep 60; done; cat "{{inbox}}/verdict-implementer-1.md". Use matching numbers and ruling files for stops. On Claude Code run waits as background commands; the host wakes the session on exit and ending the turn after starting one is allowed. On Codex keep every wait in the same turn and never end it to wait. CONTINUE starts the next section; PAUSE ends for compaction; CLOSE stops; otherwise end only after the push stop's ruling.
Models: {{model_rules}}
Standing rules: {{standing_rules}} Read "{{rules_path}}". Follow the protocol's authority and atomic-write rules. Report tokens, never stop because of them.
```

## CONTINUE prompt

```text
Continue as the Implementer for {{unit}} from section <n> through the last section. Work in "{{working_directory}}" on {{branch}}, base head {{base_head}}. Re-read "{{protocol_path}}", "{{handoff_path}}", "{{plan_path}}" and every file in "{{inbox}}" in name order, then check git log. Act on the newest verdict or ruling; if your newest checkpoint or stop has no answer, wait for it. The handoff grants every remaining section, one at a time, each after CONTINUE, including staging by name and committing; push, PR and merge still need the user's own word. On Claude Code run the protocol's wait loop as a background command; the host wakes the session and ending the turn after starting it is allowed. On Codex keep the turn alive through every wait and never end it to wait. All task, stop, done, model and standing rules remain binding; end otherwise only at PAUSE, CLOSE or after the push stop's ruling.
```
