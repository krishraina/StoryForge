# StoryForge Workflow

## Overview

StoryForge follows a structured editorial workflow that combines participant management, AI-assisted generation, editorial review, repository management, and exports.

AI generation is only one stage of the overall operational process.

---

# Complete Workflow

```
Participants
      │
      ▼
Workspace
      │
      ▼
Prompt Builder
      │
      ▼
Gemini Generation
      │
      ▼
Draft
      │
      ▼
Review Queue
      │
      ▼
Approved
      │
      ▼
Repository
      │
      ▼
Export Center
```

---

# Participant Stage

Participants are created or imported before generation begins.

Each participant contains structured information such as:

- Identity
- Program
- Cohort
- Domain
- Background
- Achievements
- Challenges
- Outcomes
- Consent level

This structured information becomes the context supplied to the Prompt Builder.

---

# AI Generation Stage

The Workspace coordinates generation.

Generation sequence:

1. Load participant.
2. Select story format.
3. Build structured prompt.
4. Submit request to Gemini.
5. Receive generated story.
6. Save draft.

Story generation never bypasses the draft stage.

---

# Draft Stage

Drafts support:

- Manual editing
- Regeneration
- Version tracking
- Editorial notes

This allows AI output to be refined before publication.

---

# Review Workflow

Drafts are submitted to the Review Queue.

Possible outcomes:

```
Draft
   │
   ▼
Submitted
   │
   ├────────► Rejected
   │              │
   │              ▼
   │           Draft
   │
   ▼
Approved
   │
   ▼
Published
```

---

# Repository

Published stories become searchable through the Repository.

Repository functions include:

- Search
- Filtering
- Status tracking
- Story history
- Export integration

---

# Export Workflow

Repository data is passed to the Export Service.

Exports currently support structured Excel output suitable for reporting and archival purposes.

---

# Batch Operations

Large-scale generation follows a dedicated workflow.

```
CSV Import
      │
      ▼
Validation
      │
      ▼
Batch Job Creation
      │
      ▼
Sequential AI Requests
      │
      ▼
Draft Stories
      │
      ▼
Repository
```

Batch generation is intentionally sequential to remain compatible with Gemini API quotas and simplify recovery from interrupted jobs.

---

# Operational Benefits

The workflow provides:

- Repeatable story generation
- Editorial oversight
- Consistent repository management
- Reliable batch processing
- Traceable story lifecycle
- Controlled publication process

StoryForge therefore operates as an editorial platform rather than a text-generation tool.