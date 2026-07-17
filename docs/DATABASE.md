# StoryForge Database Design

## Overview

StoryForge uses a single SQLite database as the central persistence layer for the entire platform.

Every feature—including participant management, AI story generation, editorial review, repository management, audit logging, and batch operations—reads from and writes to this database through the centralized `Database Service`.

The application intentionally avoids multiple databases to maintain consistency, simplify deployment, and reduce maintenance complexity.

---

# Database Architecture

```
                StoryForge UI
                     │
                     ▼
          Database Service (services/db_service.py)
                     │
                     ▼
              SQLite Database
                     │
     ┌───────────────┼────────────────┐
     ▼               ▼                ▼
Participants      Stories        Batch Jobs
                     │
                     ▼
                Audit Log
```

---

# Database Tables

The current implementation contains four primary application tables.

| Table | Purpose |
|--------|----------|
| participants | Stores participant information |
| stories | Stores generated stories and editorial workflow |
| batch_jobs | Tracks batch generation jobs |
| audit_log | Records important application actions |

SQLite also contains the internal `sqlite_sequence` table used for AUTOINCREMENT values.

---

# Participants Table

The `participants` table stores every individual whose story can be generated.

## Fields

| Field | Description |
|--------|-------------|
| id | Primary Key |
| name | Participant name |
| email | Email address |
| program | Program or initiative |
| cohort | Cohort or batch |
| domain | Professional domain |
| background | Background information |
| achievements | Key achievements |
| challenges | Challenges faced |
| outcomes | Outcomes or impact |
| consent_level | Consent level for story generation |
| linkedin_url | LinkedIn profile |
| import_batch_id | Batch import reference |
| created_at | Creation timestamp |
| updated_at | Last modification timestamp |

This table acts as the primary input source for AI story generation.

---

# Stories Table

The `stories` table stores all generated content throughout its lifecycle.

Each story remains associated with its participant and progresses through the editorial workflow.

The implementation tracks:

- Participant association
- Story format
- Generated content
- AI model used
- Prompt used for generation
- Story status
- Version history
- Editorial notes
- Reviewer information
- Batch generation reference
- Word count
- Creation and update timestamps

This table is the operational heart of StoryForge.

---

# Batch Jobs Table

Batch generation is managed through the `batch_jobs` table.

Each batch job records the progress of a large generation request.

Typical information includes:

- Job status
- Total participants
- Completed stories
- Failed generations
- Retry information
- Progress tracking
- Start and completion timestamps

This allows StoryForge to recover gracefully from interruptions while keeping users informed of generation progress.

---

# Audit Log Table

StoryForge maintains an audit log to improve traceability.

Typical logged events include:

- Story generation
- Story updates
- Review actions
- Batch operations
- Export events

Maintaining an audit trail makes the platform easier to debug and extend.

---

# Data Relationships

The implemented relationships are straightforward.

```
Participant
      │
      │ 1
      ▼
Stories
      │
      │ many
      ▼
Batch Job (optional)

Stories
      │
      ▼
Audit Log Entries
```

A participant may have multiple generated stories.

Stories may optionally belong to a batch generation job.

Important actions performed on stories are recorded in the audit log.

---

# Story Lifecycle

Every story progresses through a controlled editorial workflow.

```
Participant

      │

      ▼

Generate

      │

      ▼

Draft

      │

      ▼

Submitted

      │

      ▼

Approved

      │

      ▼

Published

      │

      ▼

Repository

      │

      ▼

Export
```

This workflow ensures AI-generated content is reviewed before publication.

---

# Database Access Pattern

StoryForge follows a strict layered architecture.

```
Pages

      │

      ▼

Database Service

      │

      ▼

SQLite
```

Pages never execute SQL directly.

All database operations are centralized inside `services/db_service.py`, improving maintainability and ensuring consistent behavior throughout the application.

---

# Design Decisions

The database architecture intentionally uses:

- A single SQLite database
- Centralized data access
- Participant-centric story generation
- Version-controlled stories
- Editorial workflow tracking
- Batch job persistence
- Audit logging

These choices support the application's modular architecture while keeping deployment lightweight.

---

# Future Enhancements

The current schema can be extended to support:

- User authentication
- Role-based permissions
- Multi-reviewer workflows
- Story tagging
- Attachment management
- PostgreSQL migration
- Cloud-hosted databases

The existing service layer allows these enhancements with minimal impact on the user interface.

---

# Summary

StoryForge's database is designed around a participant-first storytelling workflow.

By combining participant management, AI generation, editorial review, batch processing, repository management, and audit logging within a single SQLite database, the platform maintains consistency while remaining simple to deploy and maintain.