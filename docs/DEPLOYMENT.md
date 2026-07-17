# StoryForge Deployment Guide

## Overview

This document explains how to set up, configure, and run StoryForge in a local development environment. It also provides guidance for deploying the application using Streamlit Community Cloud.

StoryForge is designed to be lightweight, requiring only Python, a Gemini API key, and the project dependencies.

---

# System Requirements

## Software

- Python 3.11 or later
- Git
- Streamlit
- Google Gemini API Key

---

## Recommended Environment

- Visual Studio Code
- Python Virtual Environment (`venv`)
- Windows, macOS, or Linux

---

# Project Setup

Clone the repository:

```bash
git clone https://github.com/<your-username>/StoryForge.git
cd StoryForge
```

---

# Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

# Install Dependencies

Install the required Python packages.

```bash
pip install -r requirements.txt
```

---

# Configure Environment Variables

Create a `.env` file in the project root.

Example:

```env
GEMINI_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-2.5-flash
APP_TITLE=StoryForge
APP_VERSION=3.0
```

Never commit your actual `.env` file to version control.

---

# Run the Application

Start the Streamlit server.

```bash
streamlit run app.py
```

The application will open in your default web browser.

Typical local address:

```
http://localhost:8501
```

---

# Project Structure

```
StoryForge/
│
├── app.py
├── pages/
├── services/
├── components/
├── core/
├── outputs/
├── docs/
├── requirements.txt
├── README.md
└── .env
```

---

# Database

StoryForge uses SQLite for local persistence.

The database is automatically created if it does not already exist.

Database location:

```
outputs/
```

No additional database server is required.

---

# Streamlit Deployment

StoryForge can be deployed using Streamlit Community Cloud.

Deployment steps:

1. Push the repository to GitHub.
2. Create a new Streamlit Community Cloud application.
3. Connect the GitHub repository.
4. Set `app.py` as the entry point.
5. Add the required environment variables under **Secrets**.
6. Deploy the application.

---

# Required Secrets

At minimum, configure:

```
GEMINI_API_KEY
```

Additional configuration values may also be provided if needed.

---

# Troubleshooting

## Missing Dependencies

If a package cannot be imported:

```bash
pip install -r requirements.txt
```

---

## Invalid API Key

If story generation fails:

- Verify the Gemini API key.
- Ensure the key is active.
- Confirm it is correctly stored in the `.env` file or deployment secrets.

---

## Database Issues

If the SQLite database becomes corrupted:

1. Back up the existing database.
2. Remove the corrupted database file.
3. Restart StoryForge to create a new database.

---

## Port Already in Use

If Streamlit reports the port is unavailable:

```bash
streamlit run app.py --server.port 8502
```

---

# Production Notes

StoryForge currently targets:

- Single-user workflows
- Local execution
- Lightweight deployment
- AI-assisted editorial operations

The modular architecture allows future enhancements such as authentication, cloud databases, and multi-user collaboration.

---

# Deployment Checklist

Before deployment, verify the following:

- Repository is up to date.
- `.env` is excluded from Git.
- Dependencies are listed in `requirements.txt`.
- Documentation is complete.
- Secrets are configured.
- Application launches successfully.
- Story generation works correctly.
- Export functionality has been tested.

---

# Summary

StoryForge is designed for straightforward deployment with minimal setup. By combining Streamlit, SQLite, and the Gemini API, the application can be run locally or deployed to Streamlit Community Cloud without requiring additional infrastructure.