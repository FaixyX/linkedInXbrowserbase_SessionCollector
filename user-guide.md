# LinkedIn Session Capture API - User Guide

## API Endpoints Overview

### 1. GET `/` - Health Check
Check if the API is running.

**Request:**
```bash
GET http://localhost:8000/
```

**Response:**
```json
{
  "status": "LinkedIn Session Capture API is running."
}
```

---

### 2. POST `/start-session` - Start a New Session ⭐
Creates a Browserbase session, opens LinkedIn login page, and returns the debugger URL.

**Request:**
```bash
POST http://localhost:8000/start-session
Content-Type: application/json
```

**No body required** - Just send an empty POST request.

**Response:**
```json
{
  "message": "Session created and LinkedIn login page opened. Please use the debugger URL to log in.",
  "session_id": "15316d2b-1eea-422c-b6b3-d5ec425e498c",
  "debugger_url": "https://browserbase.com/sessions/xxx/debugger",
  "status": "ready_for_login"
}
```

**Important:** The `debugger_url` is the **Browserbase live preview URL**. Use this to view and interact with the browser session.

**Example (cURL):**
```bash
curl -X POST http://localhost:8000/start-session
```

**Example (JavaScript/Frontend):**
```javascript
const response = await fetch('http://localhost:8000/start-session', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log('Session ID:', data.session_id);
console.log('Debugger URL:', data.debugger_url);

// Open debugger URL for user to log in
window.open(data.debugger_url, '_blank');
```

---

### 3. POST `/finalize-session` - Capture Session Data ⭐
Captures LinkedIn session data (cookies, li_at token, etc.) after the user has logged in.

**Request:**
```bash
POST http://localhost:8000/finalize-session
Content-Type: application/json

{
  "session_id": "15316d2b-1eea-422c-b6b3-d5ec425e498c"
}
```

**Response:**
```json
{
  "message": "Session finalized successfully.",
  "captured_data": {
    "li_at_present": true,
    "userAgent_length": 150
  }
}
```

**Example (cURL):**
```bash
curl -X POST http://localhost:8000/finalize-session \
  -H "Content-Type: application/json" \
  -d '{"session_id": "15316d2b-1eea-422c-b6b3-d5ec425e498c"}'
```

**Example (JavaScript/Frontend):**
```javascript
const response = await fetch('http://localhost:8000/finalize-session', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    session_id: '15316d2b-1eea-422c-b6b3-d5ec425e498c'
  })
});

const data = await response.json();
console.log('LinkedIn data captured:', data.captured_data);
```

---

### 4. GET `/health` - System Health Check
Checks if Redis and Browserbase are working.

**Request:**
```bash
GET http://localhost:8000/health
```

**Response (if healthy):**
```json
{
  "status": "ok",
  "dependencies": {
    "redis": "healthy",
    "browserbase": "healthy"
  }
}
```

---

## Complete Workflow

### Step 1: Start Session
```bash
POST /start-session
```
- Creates Browserbase session
- Opens LinkedIn login page
- Returns `session_id` and `debugger_url`

### Step 2: User Logs In
- Open the `debugger_url` in a browser
- User logs into LinkedIn
- Session remains active

### Step 3: Finalize Session
```bash
POST /finalize-session
{
  "session_id": "your-session-id-from-step-1"
}
```
- Captures session data (cookies, li_at token, userAgent)
- Sends data to Bubble.io
- Returns captured data summary

---

## Frontend Integration Example

```javascript
// Step 1: Start session
async function startLinkedInSession() {
  const response = await fetch('http://localhost:8000/start-session', {
    method: 'POST'
  });
  
  const data = await response.json();
  
  // Store session_id for later
  localStorage.setItem('linkedin_session_id', data.session_id);
  
  // Show debugger URL to user
  const debuggerUrl = data.debugger_url;
  window.open(debuggerUrl, '_blank');
  
  return data;
}

// Step 2: Finalize session (call after user logs in)
async function finalizeLinkedInSession() {
  const sessionId = localStorage.getItem('linkedin_session_id');
  
  const response = await fetch('http://localhost:8000/finalize-session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      session_id: sessionId
    })
  });
  
  const data = await response.json();
  console.log('Captured data:', data.captured_data);
  
  return data;
}

// Usage:
// 1. Call startLinkedInSession() - user logs in through debugger URL
// 2. After user logs in, call finalizeLinkedInSession()
```

---

## Quick Reference

| Endpoint | When to Use | Returns |
|----------|-------------|---------|
| `POST /start-session` | **First** - To create a new session | `session_id` + `debugger_url` (Browserbase live preview) |
| `POST /finalize-session` | **After** user logs in | Captured LinkedIn data |
| `GET /health` | Anytime - To check system status | Health status |
| `GET /` | Anytime - To verify API is running | Status message |

## Important Notes

- The `debugger_url` from `/start-session` is the **Browserbase live preview URL** where users can see and interact with the browser session
- The session remains alive until the user successfully logs in (automatic termination)
- Always store the `session_id` from `/start-session` to use with `/finalize-session`
- The `/finalize-session` endpoint should be called after the user has logged in through the debugger URL

