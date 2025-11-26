# Document Insight Extraction - Frontend

React-based frontend application for the Document Insight Extraction system, built with TypeScript, Vite, and AWS Cloudscape Design System.

## Features

- **Document Upload**: Upload PDF documents with real-time progress tracking via WebSocket
- **Document Management**: View and manage uploaded documents
- **Insight Extraction**: Extract structured insights from documents using natural language prompts
- **Authentication**: Secure user authentication with AWS Cognito
- **Responsive UI**: Modern, accessible interface using Cloudscape Design System

## Prerequisites

- Node.js 18+ and npm
- AWS Cognito User Pool (configured in backend)
- API Gateway endpoints (REST and WebSocket)

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

3. Update the `.env` file with your AWS configuration:
```
VITE_USER_POOL_ID=your-user-pool-id
VITE_USER_POOL_CLIENT_ID=your-client-id
VITE_API_ENDPOINT=https://your-api-gateway-url
VITE_WSS_ENDPOINT=wss://your-websocket-url
```

## Development

Run the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:5173`

## Build

Build for production:
```bash
npm run build
```

The built files will be in the `dist` directory.

## Project Structure

```
src/
├── components/
│   ├── Common/           # Shared components (Header, Layout)
│   ├── DocumentUpload/   # Document upload components
│   └── InsightExtraction/ # Insight extraction components
├── pages/                # Page components
├── services/             # API and service modules
│   ├── api.ts           # REST API client
│   ├── auth.ts          # Cognito authentication
│   └── websocket.ts     # WebSocket service
├── types/               # TypeScript type definitions
├── App.tsx              # Main app component with routing
└── main.tsx             # Application entry point
```

## Key Components

### Document Upload
- **UploadButton**: File selection and upload initiation
- **UploadProgress**: Real-time progress tracking via WebSocket
- **DocumentList**: Display and manage uploaded documents

### Insight Extraction
- **DocumentSelector**: Select a document for insight extraction
- **PromptInput**: Enter natural language prompts
- **InsightDisplay**: Display extracted insights with export options

## Technologies

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Client-side routing
- **AWS Cloudscape Design System** - UI components
- **Axios** - HTTP client
- **Amazon Cognito Identity JS** - Authentication

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_USER_POOL_ID` | AWS Cognito User Pool ID |
| `VITE_USER_POOL_CLIENT_ID` | AWS Cognito User Pool Client ID |
| `VITE_API_ENDPOINT` | API Gateway REST endpoint URL |
| `VITE_WSS_ENDPOINT` | API Gateway WebSocket endpoint URL |

## Authentication Flow

1. User signs up or signs in via Cognito
2. JWT tokens are stored in localStorage
3. Tokens are automatically added to API requests
4. Token refresh is handled automatically
5. WebSocket connections include auth token in query string

## WebSocket Integration

The application uses WebSocket for real-time document processing updates:

- Connects when document upload starts
- Receives progress updates every 10 pages
- Displays completion or error status
- Automatically reconnects on connection loss

## API Integration

All API calls include authentication headers automatically via Axios interceptors. The API service handles:

- Presigned URL generation for S3 uploads
- Document listing
- Insight extraction
- Cached insight retrieval

## License

See LICENSE file in the root directory.
