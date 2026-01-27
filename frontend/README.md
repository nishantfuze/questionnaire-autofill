# Questionnaire Autofill Frontend

A clean, simple Next.js frontend for the Bank Questionnaire Autofill Agent.

## Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Prerequisites

Make sure the backend is running:

```bash
cd ../backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Environment Variables

Create a `.env.local` file (already included):

```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Features

- Drag and drop CSV upload
- Real-time processing status
- Confidence score summary (High/Medium/Low/Insufficient)
- One-click CSV download
- API health check
- Error handling with troubleshooting tips

## Tech Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS

## Project Structure

```
frontend/
├── app/
│   ├── globals.css      # Tailwind imports
│   ├── layout.tsx       # Root layout
│   └── page.tsx         # Main UI page
├── components/
│   ├── FileUpload.tsx   # Drag & drop upload
│   └── Spinner.tsx      # Loading spinner
├── lib/
│   ├── api.ts           # API client functions
│   └── download.ts      # CSV download helper
├── .env.local           # Environment variables
├── package.json
├── tailwind.config.js
└── tsconfig.json
```
