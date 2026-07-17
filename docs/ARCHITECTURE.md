# StoryForge Architecture

## Overview

StoryForge is a modular AI-assisted storytelling platform built around an operational workflow rather than a conversational AI interface.

The platform manages the complete lifecycle of participant stories—from participant onboarding and AI generation to editorial review, publication, repository management, batch operations, and exports.

The architecture emphasizes maintainability, modularity, and production readiness by separating presentation, business logic, AI integration, persistence, and export functionality into dedicated modules.

---

# System Architecture

```
                           StoryForge

                    Streamlit Presentation Layer
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Dashboard                                                   │
│  Participants                                                │
│  Workspace                                                   │
│  Review Queue                                                │
│  Repository                                                  │
│  Export Center                                               │
│  Batch Operations                                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼

                    Business Service Layer

          db_service.py
          gemini_service.py
          prompt_builder.py
          batch_service.py
          export_service.py
          excel_service.py

                           │
                           ▼

                  SQLite Database + File Exports
```

---

# Architecture Layers

## Presentation Layer

The presentation layer is implemented using Streamlit.

Rather than using a chatbot interface, StoryForge organizes functionality into operational pages.

### Dashboard

Provides operational metrics and application status.

### Participants

Maintains participant records used during AI generation.

### Workspace

Primary editorial workspace for AI-assisted story generation, editing, regeneration, and draft management.

### Review Queue

Editorial approval workflow.

### Repository

Central library of completed stories.

### Export Center

Generates structured Excel exports.

### Batch Operations

Supports CSV import, batch generation, progress tracking, and recovery.

---

# Service Layer

Business logic is isolated from the user interface.

## Database Service

`services/db_service.py`

Responsibilities:

- Database initialization
- CRUD operations
- Story lifecycle
- Repository queries
- Batch persistence
- Audit logging

Every page communicates with SQLite exclusively through this service.

---

## Gemini Service

`services/gemini_service.py`

Responsibilities:

- Gemini API communication
- Sequential generation
- Retry handling
- Response processing
- Generation safeguards

The application intentionally performs sequential requests to remain compatible with Gemini Free Tier limits.

---

## Prompt Builder

`services/prompt_builder.py`

Responsibilities:

- Structured prompt construction
- Story type formatting
- Participant context assembly

Prompt generation is centralized to ensure consistency across every story.

---

## Batch Service

`services/batch_service.py`

Coordinates large-scale generation.

Responsibilities include:

- Queue execution
- Progress tracking
- Job recovery
- Failure handling

Batch execution integrates with the database so interrupted jobs can be reconciled correctly.

---

## Export Service

Responsible for preparing repository data for export.

Works together with the Excel Service to generate structured output files.

---

## Excel Service

Creates Excel workbooks from repository data while keeping spreadsheet generation isolated from application logic.

---

# Component Layer

Reusable interface components are shared across all pages.

Current shared components include:

- Theme
- Sidebar
- Badges

This avoids duplicated UI logic and ensures a consistent interface throughout the application.

---

# Data Layer

StoryForge uses a single SQLite database.

Current application tables include:

- participants
- stories
- batch_jobs
- audit_log

Using a single database guarantees consistent state across all workflows.

---

# Story Lifecycle

```
Participant
      │
      ▼
Prompt Builder
      │
      ▼
Gemini Service
      │
      ▼
Draft
      │
      ▼
Editorial Review
      │
      ▼
Approved
      │
      ▼
Repository
      │
      ▼
Export
```

---

# Batch Workflow

```
CSV Import
      │
      ▼
Participant Validation
      │
      ▼
Batch Job
      │
      ▼
Sequential Generation
      │
      ▼
Repository
      │
      ▼
Export
```

---

# Design Principles

StoryForge is intentionally designed around:

- Modular services
- Shared UI components
- Single database architecture
- Editorial workflow
- Participant-first data model
- Sequential AI generation
- Centralized configuration
- Reusable business logic

---

# Scalability

The architecture allows future enhancements including:

- Authentication
- Multi-user collaboration
- PostgreSQL
- Background workers
- REST APIs
- Cloud storage

These additions can be implemented without restructuring the existing architecture because responsibilities are already separated into dedicated modules.