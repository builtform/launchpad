---
description: Update session memory and create a detailed report file for the current session's findings
---

Scan the entire conversation for key findings, decisions, plans, architectural choices, and important outcomes from this session.

Then perform these two actions:

## 1. Update MEMORY.md

Add a concise entry to the project's auto-memory file (`MEMORY.md` in the project memory directory). Follow these rules:

- Keep the total file under 200 lines (it gets truncated beyond that)
- Add a new section header (## or bold heading) describing the topic
- Include: status, key decisions, important file paths, and a link to the detailed report
- If an entry for this topic already exists, update it rather than duplicating
- Check existing content first to avoid duplicates

## 2. Create a Detailed Report

Save the full plan, analysis, or findings to a separate file in the same memory directory:

- Auto-generate the filename in kebab-case from the session topic (e.g., `rag-pipeline-redesign.md`, `auth-system-audit.md`)
- Include all details: rationale, alternatives considered, implementation notes, open questions
- Structure the report with clear headings and sections
- If a report file for this topic already exists, update it rather than creating a new one

## 3. Confirm

After both files are written, report back:

- What was added/updated in MEMORY.md
- The full path of the report file created
- A one-line summary of what was captured
