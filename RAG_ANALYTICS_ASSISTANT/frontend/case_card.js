// case_card.js — Phase 6 Step 6.4
//
// Handles the Jira escalation UI — the card shown when the AI cannot
// answer a question confidently.
//
// The flow:
//   1. AI returns type="escalation" with escalation_id and message
//   2. app.js calls renderEscalationCard() — shows Yes/No buttons
//   3. User clicks Yes or No → confirmEscalation() is called
//   4. Yes → POST /ask/confirm-escalation → Jira story created → link shown
//   4. No  → POST /ask/confirm-escalation → polite decline shown


function renderEscalationCard(escalationId, message) {
    // escalationId: string → UUID from main.pending_escalations
    //                         sent to /ask/confirm-escalation to identify this escalation
    // message: string      → the human-readable message from agent_prompt.py
    //                         e.g. "I was unable to find a reliable answer..."

    const messages = document.getElementById('chatMessages');
    const card = document.createElement('div');
    card.className = 'escalation-card';
    card.id = `escalation-${escalationId}`;
    // unique ID so confirmEscalation() can find and update this specific card

    card.innerHTML = `
        <div class="escalation-message">${message.replace(/\n/g, '<br>')}</div>
        <!-- replace \n with <br> so the message renders with proper line breaks -->
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
    // scroll down so the escalation card is visible
}


async function confirmEscalation(escalationId, confirmed) {
    // escalationId: string → the UUID identifying this pending escalation
    // confirmed: boolean   → true if user clicked Yes, false if clicked No

    const card = document.getElementById(`escalation-${escalationId}`);
    const actions = card.querySelector('.escalation-actions');
    actions.innerHTML = '<span class="loading">Processing...</span>';
    // replace Yes/No buttons with a loading indicator while the request runs
    // this prevents double-clicks and gives visual feedback

    try {
        const response = await fetch('/ask/confirm-escalation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                escalation_id: escalationId,
                // note: snake_case — matches the ConfirmRequest Pydantic model in routes.py
                confirmed
                // shorthand for confirmed: confirmed
            })
        });
        const data = await response.json();

        if (confirmed && data.jira_key) {
            // user said Yes and Jira story was created successfully
            actions.innerHTML = `
                <div class="escalation-success">
                    Done. Jira story <strong>${data.jira_key}</strong> has been created.
                    Your analytics team will investigate and respond there.<br>
                    <a href="${data.jira_url}" target="_blank" class="jira-link">
                        View story: ${data.jira_key} →
                    </a>
                </div>
            `;
            // target="_blank" opens the Jira story in a new tab
        } else {
            // user said No — show the polite decline message from the API
            actions.innerHTML = `
                <div class="escalation-declined">
                    ${data.message}
                </div>
            `;
        }

    } catch (err) {
        // network error or server error — show a retry message
        actions.innerHTML = '<span class="error">Something went wrong. Please try again.</span>';
        console.error('Escalation confirmation error:', err);
    }
}