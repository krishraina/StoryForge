# StoryForge User Guide

## Introduction

Welcome to StoryForge.

StoryForge is an AI-assisted storytelling platform designed to manage the complete lifecycle of impact stories—from participant management and AI generation to editorial review, repository management, and exports.

This guide explains each section of the application and the recommended workflow for creating and managing stories.

---

# Dashboard

The Dashboard provides an overview of the application.

It displays high-level information about:

- Total participants
- Stories generated
- Draft stories
- Stories awaiting review
- Published stories
- Repository statistics

The Dashboard serves as the starting point for daily operations.

---

# Participants

The Participants page is used to manage the people whose stories will be generated.

## Features

- Add new participants
- Edit participant information
- Delete participants
- Search participants
- View participant details

Typical participant information includes:

- Name
- Organization
- Department
- Role
- Location
- Consent status

Participants must exist before stories can be generated.

---

# Workspace

The Workspace is where AI story generation takes place.

## Story Generation

1. Select a participant.
2. Choose one or more story formats.
3. Start story generation.
4. Wait for the AI response.
5. Review the generated content.

Generated stories are automatically saved as drafts.

---

## Editing Drafts

Users can:

- Edit generated text
- Regenerate stories
- Save changes
- Submit stories for review

This allows AI-generated content to be refined before publication.

---

# Review Queue

The Review Queue contains stories awaiting editorial approval.

Available actions include:

- Review stories
- Approve stories
- Reject stories
- Return stories for revision

Only approved stories are published to the Repository.

---

# Repository

The Repository stores all published stories.

Users can:

- Search stories
- Filter stories
- Browse published content
- Review story history

The Repository acts as the central archive for completed work.

---

# Exports

The Export Center allows users to generate reports from repository data.

Supported exports include:

- Excel exports
- Repository reports

Exported files are generated using the centralized Export Service.

---

# Batch Operations

Batch Operations enable large-scale story generation.

Typical workflow:

1. Prepare a CSV file containing participant data.
2. Import the CSV into StoryForge.
3. Validate imported records.
4. Start batch generation.
5. Monitor progress.
6. Review generated stories.

Batch generation processes participants sequentially to improve reliability and comply with AI API limits.

---

# Recommended Workflow

For the best experience, follow this sequence:

```
Participants
      │
      ▼
Workspace
      │
      ▼
Draft
      │
      ▼
Review Queue
      │
      ▼
Repository
      │
      ▼
Exports
```

This ensures that every generated story passes through editorial review before publication.

---

# Tips

- Verify participant information before generating stories.
- Review AI-generated content before approval.
- Use the Repository to search previously published stories.
- Export data regularly if maintaining offline records.
- Monitor Batch Operations during large generation jobs.

---

# Troubleshooting

## Story generation fails

- Check that a valid Gemini API key is configured.
- Verify your internet connection.
- Ensure API usage limits have not been exceeded.

---

## Draft not visible

- Confirm the story was successfully generated.
- Refresh the Workspace if necessary.
- Check the Review Queue or Repository for stories that may have been moved.

---

## Export fails

- Ensure there are stories available to export.
- Verify that the output directory is writable.

---

# Best Practices

- Keep participant information up to date.
- Review all AI-generated content before publication.
- Use batch generation for large participant lists.
- Export important reports regularly.
- Back up the SQLite database periodically.

---

# Support

StoryForge is designed as a modular, maintainable application.

For technical issues:

1. Verify the deployment configuration.
2. Review the application logs.
3. Confirm environment variables are correctly configured.
4. Ensure all required dependencies are installed.

---

# Summary

StoryForge combines participant management, AI-assisted content generation, editorial review, repository management, batch processing, and exports into a single operational workflow.

Following the recommended workflow helps maintain consistency, improve content quality, and ensure a smooth storytelling process.