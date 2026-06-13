# Phase 6 — Frontend Chat UI

**Steps:** 5  
**Goal:** Build a professional three-panel chat interface. Stream answers, show source citations, handle the Jira escalation flow. Demoable to a VP in an interview.

---

## Step 6.1 — Build frontend/index.html — three panel layout

**What you do:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Analytics Assistant</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="layout">

    <!-- Left panel: knowledge base documents -->
    <aside class="panel-left" id="docList">
      <div class="panel-header">Knowledge base</div>
      <ul id="docListItems"></ul>
    </aside>

    <!-- Centre panel: chat conversation -->
    <main class="panel-centre">
      <div class="chat-header">
        <span>Analytics Assistant</span>
        <button id="newChatBtn" onclick="newConversation()">New conversation</button>
        <button id="themeBtn" onclick="toggleTheme()">Dark mode</button>
      </div>
      <div class="chat-messages" id="chatMessages"></div>
      <div class="chat-input-row">
        <textarea id="questionInput" placeholder="Ask a question..." rows="2"></textarea>
        <button id="sendBtn" onclick="sendQuestion()">Send</button>
      </div>
    </main>

    <!-- Right panel: source citations -->
    <aside class="panel-right" id="sourcesPanel">
      <div class="panel-header">Sources</div>
      <div id="sourcesList"></div>
    </aside>

  </div>
  <script src="case_card.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

**style.css** key rules:
```css
:root {
  --bg: #ffffff;
  --text: #1a1a1a;
  --border: #e0e0e0;
  --panel-bg: #f8f8f8;
  --accent: #0066cc;
}
body.dark-mode {
  --bg: #1a1a1a;
  --text: #f0f0f0;
  --border: #333333;
  --panel-bg: #242424;
}
.layout {
  display: flex;
  height: 100vh;
  background: var(--bg);
  color: var(--text);
}
.panel-left  { width: 220px; flex-shrink: 0; border-right: 1px solid var(--border); }
.panel-centre { flex: 1; display: flex; flex-direction: column; }
.panel-right { width: 280px; flex-shrink: 0; border-left: 1px solid var(--border); }
.chat-messages { flex: 1; overflow-y: auto; padding: 1rem; }
.chat-input-row { display: flex; gap: 8px; padding: 1rem; border-top: 1px solid var(--border); }
textarea { flex: 1; resize: none; }

/* Mobile: hide side panels */
@media (max-width: 768px) {
  .panel-left, .panel-right { display: none; }
}
```

**Verify:**
Open `localhost:8000` — three panels visible. Resize to 600px wide — side panels hide, only chat remains.

---

## Step 6.2 — Build frontend/app.js — streaming chat and source citations

**What you do:**

```javascript
const API_BASE = '';  // same origin — FastAPI serves both

function getSessionId() {
    let id = sessionStorage.getItem('session_id');
    if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem('session_id', id);
    }
    return id;
}

function getHistory() {
    return JSON.parse(localStorage.getItem('chat_history') || '[]');
}

function addToHistory(question, answer) {
    const history = getHistory();
    history.push({role: 'user', content: question});
    history.push({role: 'assistant', content: answer});
    localStorage.setItem('chat_history', JSON.stringify(history.slice(-10)));
}

async function sendQuestion() {
    const input = document.getElementById('questionInput');
    const question = input.value.trim();
    if (!question || question.length < 5) return;

    input.value = '';
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Thinking...';

    appendMessage('user', question);
    clearSources();

    try {
        // try streaming endpoint first
        const response = await fetch(`${API_BASE}/ask/stream`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question,
                session_id: getSessionId(),
                history: getHistory()
            })
        });

        if (!response.ok) {
            // fall back to non-streaming /ask
            const data = await fetch(`${API_BASE}/ask`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({question, session_id: getSessionId()})
            }).then(r => r.json());

            if (data.type === 'escalation') {
                renderEscalationCard(data.escalation_id, data.message);
                return;
            }
            appendMessage('assistant', data.answer);
            renderSources(data.sources || []);
            addToHistory(question, data.answer);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const bubble = appendMessage('assistant', '');
        let fullAnswer = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            const token = decoder.decode(value);
            fullAnswer += token;
            bubble.textContent += token;
        }

        addToHistory(question, fullAnswer);

    } catch (err) {
        appendMessage('system', 'Something went wrong. Please try again.');
        console.error(err);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

function appendMessage(role, text) {
    const messages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message message-${role}`;
    div.textContent = text;
    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'});
    div.appendChild(time);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

function renderSources(sources) {
    const panel = document.getElementById('sourcesList');
    panel.innerHTML = '';
    sources.forEach((s, i) => {
        const card = document.createElement('div');
        card.className = 'source-card';
        card.innerHTML = `
            <div class="source-title">[Source ${i+1}] ${s.source || 'unknown'}</div>
            <div class="source-score">Match: ${Math.round((s.score || 0) * 100)}%</div>
            <div class="source-preview">${(s.preview || '').substring(0, 150)}</div>
        `;
        panel.appendChild(card);
    });
}

function clearSources() {
    document.getElementById('sourcesList').innerHTML = '';
}

function newConversation() {
    localStorage.removeItem('chat_history');
    sessionStorage.removeItem('session_id');
    document.getElementById('chatMessages').innerHTML = '';
    clearSources();
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
}

// Keyboard shortcut: Enter to send, Shift+Enter for newline
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('questionInput');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    // restore theme
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
    }

    // load document list from /health
    fetch('/health').then(r => r.json()).then(data => {
        // populate left panel if health returns doc names
    });
});
```

**Verify:**

Ask a question → tokens stream one by one → message appears progressively.

---

## Step 6.3 — Add conversation history and session management

Already built in Step 6.2 via `getHistory()`, `addToHistory()`, and passing history to the API.

**Verify:**
1. Ask "What is our APAC discount?"
2. Ask "Can you give me more detail on that?"
3. The second answer references the first — LLM has history context.
4. Click "New conversation" — history clears, second question no longer references the first.

---

## Step 6.4 — Build frontend/case_card.js — Jira escalation UI

**What you do:**

```javascript
function renderEscalationCard(escalationId, message) {
    const messages = document.getElementById('chatMessages');
    const card = document.createElement('div');
    card.className = 'escalation-card';
    card.id = `escalation-${escalationId}`;
    card.innerHTML = `
        <div class="escalation-message">${message.replace(/\n/g, '<br>')}</div>
        <div class="escalation-actions">
            <button class="btn-yes" onclick="confirmEscalation('${escalationId}', true)">
                Yes, create a Jira story
            </button>
            <button class="btn-no" onclick="confirmEscalation('${escalationId}', false)">
                No, thank you
            </button>
        </div>
    `;
    messages.appendChild(card);
    messages.scrollTop = messages.scrollHeight;
}

async function confirmEscalation(escalationId, confirmed) {
    const card = document.getElementById(`escalation-${escalationId}`);
    const actions = card.querySelector('.escalation-actions');
    actions.innerHTML = '<span class="loading">Processing...</span>';

    try {
        const response = await fetch('/ask/confirm-escalation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({escalation_id: escalationId, confirmed})
        });
        const data = await response.json();

        if (confirmed && data.jira_key) {
            actions.innerHTML = `
                <div class="escalation-success">
                    Done. Jira story <strong>${data.jira_key}</strong> has been created.
                    Your analytics team will investigate and respond there.<br>
                    <a href="${data.jira_url}" target="_blank" class="jira-link">
                        View story: ${data.jira_key} →
                    </a>
                </div>
            `;
        } else {
            actions.innerHTML = `
                <div class="escalation-declined">
                    ${data.message}
                </div>
            `;
        }
    } catch (err) {
        actions.innerHTML = '<span class="error">Something went wrong. Please try again.</span>';
    }
}
```

**Verify:**
1. Ask a question that triggers escalation (set SIMILARITY_THRESHOLD=0.99 temporarily)
2. Escalation card appears with Yes and No buttons
3. Click Yes → Jira link appears with correct story key
4. Open another escalation, click No → polite message, Jira board has no new story

---

## Step 6.5 — Final polish and demo preparation

**What you do:**

CSS additions:
```css
.message { margin: 8px 0; padding: 10px 14px; border-radius: 12px; max-width: 80%; }
.message-user      { background: var(--accent); color: white; margin-left: auto; }
.message-assistant { background: var(--panel-bg); border: 1px solid var(--border); }
.message-time      { font-size: 11px; opacity: 0.6; display: block; margin-top: 4px; }

.escalation-card { border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin: 8px 0; }
.escalation-actions { display: flex; gap: 10px; margin-top: 12px; }
.btn-yes { background: var(--accent); color: white; padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; }
.btn-no  { background: transparent; border: 1px solid var(--border); padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.jira-link { color: var(--accent); text-decoration: underline; }

.source-card { border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin: 8px; font-size: 13px; }
.source-score { color: var(--accent); font-weight: 500; }
```

**Three demo questions to prepare:**

Practice these until you can demo all three in under 3 minutes:

1. `"What is our discount policy for APAC enterprise accounts?"` → confident answer with sources in right panel
2. `"What is the CEO's annual bonus structure?"` → escalation card → click Yes → Jira link
3. `"Can you tell me more about the thresholds you mentioned?"` → follow-up using conversation history

**Verify:**

Run all three demo flows without touching the keyboard between questions. If anything requires intervention — fix it before Phase 7.

---

## Phase 6 complete checklist

- [ ] Three-panel layout at `localhost:8000`
- [ ] Mobile responsive — panels hide below 768px
- [ ] Tokens stream one by one into chat bubble
- [ ] Source cards appear in right panel with filenames and scores
- [ ] Conversation history sent to API — follow-up questions work
- [ ] New conversation button clears history and session
- [ ] Message timestamps shown
- [ ] Escalation card renders with Yes and No buttons
- [ ] Yes → Jira link shown in chat
- [ ] No → polite message, Jira never called
- [ ] Dark mode toggle works and persists on refresh
- [ ] Enter to send, Shift+Enter for newline
- [ ] Three demo flows rehearsed and working

**Next:** Phase 7 — Evaluation framework
