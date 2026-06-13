const API_BASE = '';
// empty string means same origin — FastAPI serves both frontend and API
// /ask resolves to http://localhost:8000/ask automatically


// ── Session and history management ────────────────────────────────────────

function getSessionId() {
    // returns the current session UUID from sessionStorage
    // sessionStorage clears when the tab is closed — each new tab = new session
    let id = sessionStorage.getItem('session_id');
    if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem('session_id', id);
    }
    return id;
}

function getHistory() {
    // returns conversation history from localStorage
    // localStorage persists across page refreshes
    return JSON.parse(localStorage.getItem('chat_history') || '[]');
}

function addToHistory(question, answer) {
    // saves one question/answer turn to localStorage
    const history = getHistory();
    history.push({role: 'user', content: question});
    history.push({role: 'assistant', content: answer});
    // keep last 10 messages (5 turns) to avoid localStorage limits
    localStorage.setItem('chat_history', JSON.stringify(history.slice(-10)));
}


// ── Main send function ─────────────────────────────────────────────────────

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
        // ── Use /ask endpoint — handles everything including escalation ───
        // /ask/stream does not return sources or escalation type
        // using /ask gives us the full response including sources and type
        const data = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                question,
                session_id: getSessionId(),
                history: getHistory()
                // history sent from localStorage enables multi-turn conversation
                // the API injects this into the prompt as conversation context
            })
        }).then(r => r.json());

        // ── Handle escalation ────────────────────────────────────────────
        if (data.type === 'escalation') {
            renderEscalationCard(data.escalation_id, data.message);
            return;
        }

        // ── Handle blocked input ─────────────────────────────────────────
        if (data.type === 'blocked') {
            appendMessage('system', data.message || 'Your input was blocked by the safety filter.');
            return;
        }

        // ── Handle answer ────────────────────────────────────────────────
        if (data.answer) {
            // simulate streaming by displaying the answer character by character
            const bubble = appendMessage('assistant', '');
            // create empty bubble — we fill it token by token below
            await streamText(bubble, data.answer);
            // streamText() animates the text appearing — gives streaming feel
            // even though we received the full answer in one HTTP response

            addToHistory(question, data.answer);
            // save to localStorage so the next question has this context

            renderSources(data.sources || []);
            // show source citation cards in the right panel
        }

    } catch (err) {
        appendMessage('system', 'Something went wrong. Please try again.');
        console.error(err);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}


// ── Streaming animation ────────────────────────────────────────────────────

async function streamText(element, text) {
    // animates text appearing word by word in the element
    // gives a streaming feel even when using the non-streaming /ask endpoint
    // element: the content span returned by appendMessage()
    // text: the full answer string to animate

    const words = text.split(' ');
    // split on spaces to get individual words

    for (const word of words) {
        element.textContent += (element.textContent ? ' ' : '') + word;
        // add a space before each word except the first
        await new Promise(resolve => setTimeout(resolve, 18));
        // 18ms delay between words — fast enough to feel natural
        // slow enough to see the streaming effect
        const messages = document.getElementById('chatMessages');
        messages.scrollTop = messages.scrollHeight;
        // keep scrolled to bottom as text appears
    }
}


// ── UI helper functions ────────────────────────────────────────────────────

function appendMessage(role, text) {
    // creates and appends a message bubble to the chat area
    // role: "user" | "assistant" | "system"
    // returns the content span so streamText() can append to it

    const messages = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `message message-${role}`;

    // content in a block-level div — forces timestamp below it
    const content = document.createElement('div');
    content.className = 'message-content';
    // div is block by default — no display:block needed in CSS
    content.textContent = text;
    div.appendChild(content);

    // timestamp below the content
    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit'
    });
    div.appendChild(time);

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return content;
    // return content div so streamText() appends tokens to it
    // the timestamp span stays separate and renders below
}

function renderSources(sources) {
    // renders source citation cards in the right panel
    const panel = document.getElementById('sourcesList');
    panel.innerHTML = '';

    if (!sources || sources.length === 0) return;

    sources.forEach((s, i) => {
        const card = document.createElement('div');
        card.className = 'source-card';

        // extract just the filename from the full absolute path
        // "/Users/.../docs/discount_policy.txt" → "discount_policy.txt"
        const filename = (s.source || 'unknown').split('/').pop();
        const score = s.score ? Math.round(s.score * 100) : 0;

        card.innerHTML = `
            <div class="source-title">[Source ${i+1}] ${filename}</div>
            <div class="source-score">Match: ${score}%</div>
        `;
        panel.appendChild(card);
    });
}

function clearSources() {
    document.getElementById('sourcesList').innerHTML = '';
}

function newConversation() {
    // clears everything — called when user clicks "New conversation"
    localStorage.removeItem('chat_history');
    sessionStorage.removeItem('session_id');
    document.getElementById('chatMessages').innerHTML = '';
    clearSources();
}

function toggleTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    document.getElementById('themeBtn').textContent = isDark ? 'Light mode' : 'Dark mode';
}


// ── Initialisation ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

    // Enter to send, Shift+Enter for newline
    const input = document.getElementById('questionInput');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    // restore theme preference
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark-mode');
        document.getElementById('themeBtn').textContent = 'Light mode';
    }

    // populate left panel with knowledge base filenames
    const files = [
        'discount_policy.txt',
        'kpi_definitions.txt',
        'regional_strategy_apac.txt',
        'regional_strategy_emea.txt',
        'sales_playbook.txt'
    ];
    const list = document.getElementById('docListItems');
    files.forEach(f => {
        const li = document.createElement('li');
        li.textContent = f;
        list.appendChild(li);
    });
});