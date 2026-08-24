// Global state variables
let activeSessionId = "demo_session_1";

// DOM Elements
const elSessionId = document.getElementById("session-id");
const elExamDate = document.getElementById("exam-date");
const elTopics = document.getElementById("topics");
const elBtnInit = document.getElementById("btn-init");
const elBtnReset = document.getElementById("btn-reset");
const elConsoleLogs = document.getElementById("console-logs");
const elTimelineDeck = document.getElementById("timeline-deck");
const elLoader = document.getElementById("loader");
const elToast = document.getElementById("toast");
const elToastMessage = document.getElementById("toast-message");
const elSessionInfo = document.getElementById("session-info");
const elInfoExamDate = document.getElementById("info-exam-date");
const elInfoDaysLeft = document.getElementById("info-days-left");
const elTimelineSummary = document.getElementById("timeline-summary");
const elCountCompleted = document.getElementById("count-completed");
const elCountMissed = document.getElementById("count-missed");

// Set default exam date: 15 days from today
const defaultDate = new Date();
defaultDate.setDate(defaultDate.getDate() + 15);
elExamDate.value = defaultDate.toISOString().split('T')[0];

// Set default topics for instant onboarding
elTopics.value = "Algebra\nChemistry\nHistory\nBiology\nGrammar";

// Event Listeners
elBtnInit.addEventListener("click", handleInitPlan);
elBtnReset.addEventListener("click", handleResetSession);
elSessionId.addEventListener("change", (e) => {
    activeSessionId = e.target.value.trim() || "demo_session_1";
    loadSessionState();
});

// Toast Notifications
function showToast(msg) {
    elToastMessage.textContent = msg;
    elToast.classList.remove("hidden");
    setTimeout(() => {
        elToast.classList.add("hidden");
    }, 4000);
}

// Show/Hide Loader
function setLoaderState(show) {
    if (show) {
        elLoader.classList.remove("hidden");
        document.querySelector(".status-dot").className = "status-dot yellow";
        document.querySelector(".status-text").textContent = "Agent Active";
    } else {
        elLoader.classList.add("hidden");
        document.querySelector(".status-dot").className = "status-dot green";
        document.querySelector(".status-text").textContent = "Agent Idle";
    }
}

// Get session ID helper
function getSessionId() {
    return elSessionId.value.trim() || "demo_session_1";
}

// 1. Initialize Study Plan
async function handleInitPlan() {
    const sessionId = getSessionId();
    const dateVal = elExamDate.value;
    const topicsVal = elTopics.value.trim();

    if (!dateVal) {
        showToast("Please pick an exam date.");
        return;
    }
    if (!topicsVal) {
        showToast("Please enter at least one topic.");
        return;
    }

    // Clean topics list
    const topicsList = topicsVal.split(/[\n,]+/).map(t => t.trim()).filter(t => t.length > 0);
    const topicsStr = topicsList.join(", ");

    const promptMessage = `My exam is on ${dateVal}. I need to study these topics: ${topicsStr}.`;

    setLoaderState(true);
    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                message: promptMessage
            })
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Server error occurred");
        }

        const data = await response.json();
        // Hide loader early so user can watch the Thought Chamber type out logs in real-time
        setLoaderState(false);
        
        await renderAgentTrace(data.trace);
        renderTimeline(data.state);
        updateStatistics(data.state);
        
        if (data.final_answer.startsWith("Groq API key")) {
            showToast(data.final_answer);
        }
    } catch (err) {
        showToast(err.message);
        console.error(err);
        setLoaderState(false);
    }
}

// 2. Reset Session
async function handleResetSession() {
    const sessionId = getSessionId();
    setLoaderState(true);
    try {
        const response = await fetch("/reset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId })
        });

        if (!response.ok) throw new Error("Reset request failed");

        elConsoleLogs.innerHTML = `<div class="console-welcome"><p class="console-prompt">> Session '${sessionId}' reset successfully.</p></div>`;
        
        // Reset inputs to default values
        const defaultDate = new Date();
        defaultDate.setDate(defaultDate.getDate() + 15);
        elExamDate.value = defaultDate.toISOString().split('T')[0];
        elTopics.value = "Algebra\nChemistry\nHistory\nBiology\nGrammar";

        // Hide layout components
        elSessionInfo.classList.add("hidden");
        elTimelineSummary.classList.add("hidden");
        
        elTimelineDeck.innerHTML = `
            <div class="empty-timeline">
                <i class="fa-solid fa-calendar-xmark"></i>
                <p>No active study plan. Define settings above and click "Generate Plan".</p>
            </div>`;
    } catch (err) {
        showToast(err.message);
    } finally {
        setLoaderState(false);
    }
}

// 3. Load Current State on Session Change
async function loadSessionState() {
    const sessionId = getSessionId();
    try {
        const response = await fetch(`/state/${sessionId}`);
        if (!response.ok) return;
        const state = await response.json();
        
        if (state.exam_date && state.day_plan && Object.keys(state.day_plan).length > 0) {
            elExamDate.value = state.exam_date;
            elTopics.value = state.topics.join("\n");
            renderTimeline(state);
            updateStatistics(state);
            
            elConsoleLogs.innerHTML = `<div class="console-welcome"><p class="console-prompt">> Loaded existing state for session '${sessionId}'. Ready.</p></div>`;
        } else {
            // State is empty
            elSessionInfo.classList.add("hidden");
            elTimelineSummary.classList.add("hidden");
            elTimelineDeck.innerHTML = `
                <div class="empty-timeline">
                    <i class="fa-solid fa-calendar-xmark"></i>
                    <p>No active study plan. Define settings above and click "Generate Plan".</p>
                </div>`;
        }
    } catch (err) {
        console.error("Failed to load session state", err);
    }
}

// 4. Mark Day Completed
async function completeDay(dayLabel) {
    const sessionId = getSessionId();
    setLoaderState(true);
    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                message: `I completed ${dayLabel}.`
            })
        });

        if (!response.ok) throw new Error("API call failed");

        const data = await response.json();
        setLoaderState(false);
        
        await renderAgentTrace(data.trace);
        renderTimeline(data.state);
        updateStatistics(data.state);
    } catch (err) {
        showToast(err.message);
        setLoaderState(false);
    }
}

// 5. Mark Day Missed (Triggers catch-up reshuffle)
async function missDay(dayLabel) {
    const sessionId = getSessionId();
    setLoaderState(true);
    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                message: `I missed ${dayLabel}. Please reshuffle my plan.`
            })
        });

        if (!response.ok) throw new Error("Reshuffle failed");

        const data = await response.json();
        setLoaderState(false);
        
        await renderAgentTrace(data.trace);
        renderTimeline(data.state);
        updateStatistics(data.state);
    } catch (err) {
        showToast(err.message);
        setLoaderState(false);
    }
}

// Helpers for real-time typing simulation
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function typeText(element, text, speed = 8) {
    return new Promise((resolve) => {
        let i = 0;
        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                elConsoleLogs.scrollTop = elConsoleLogs.scrollHeight;
                setTimeout(type, speed);
            } else {
                resolve();
            }
        }
        type();
    });
}

// Simple client-side Markdown parser to format bold texts, headers, and tables nicely
function parseMarkdown(text) {
    if (!text) return "";
    
    // 1. Convert headers (e.g. ### Study Plan)
    let html = text
        .replace(/^### (.*?)$/gm, '<h3 style="margin-top: 10px; margin-bottom: 5px; color: var(--secondary); font-family: var(--font-heading); font-size: 1.05rem;">$1</h3>')
        .replace(/^## (.*?)$/gm, '<h2 style="margin-top: 15px; margin-bottom: 8px; color: var(--secondary); font-family: var(--font-heading); font-size: 1.15rem;">$1</h2>')
        .replace(/^# (.*?)$/gm, '<h1 style="margin-top: 20px; margin-bottom: 10px; color: var(--secondary); font-family: var(--font-heading); font-size: 1.3rem;">$1</h1>');
        
    // 2. Convert bold formatting (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--secondary); font-weight: 600;">$1</strong>');

    // 3. Convert markdown tables into styled HTML tables
    const lines = html.split('\n');
    let inTable = false;
    let tableRows = [];
    
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        
        // Detect table row (starts and ends with |)
        if (line.startsWith('|') && line.endsWith('|')) {
            // Ignore alignment divider row: |---|---|
            if (line.match(/^\|[\s\-\|:]+\|$/)) {
                lines[i] = "";
                continue;
            }
            
            // Extract columns by splitting on |
            const cols = line.split('|')
                .map(c => c.trim())
                .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
                
            tableRows.push(cols);
            inTable = true;
            lines[i] = ""; // Clear original line
        } else {
            if (inTable && tableRows.length > 0) {
                // Construct the HTML Table
                let tableHtml = '<table class="console-table" style="border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.85rem; border: 1px solid rgba(255,255,255,0.08);">';
                
                tableRows.forEach((row, rowIdx) => {
                    const isHeader = rowIdx === 0; // Assume first row is header
                    tableHtml += `<tr style="${isHeader ? 'background: rgba(255,255,255,0.04);' : 'border-bottom: 1px solid rgba(255,255,255,0.05);'}">`;
                    
                    row.forEach(col => {
                        const tag = isHeader ? 'th' : 'td';
                        tableHtml += `<${tag} style="padding: 6px 10px; text-align: left; border: 1px solid rgba(255,255,255,0.06); font-weight: ${isHeader ? '600' : '400'}; color: ${isHeader ? 'var(--secondary)' : 'var(--text-primary)'};">${col}</${tag}>`;
                    });
                    
                    tableHtml += '</tr>';
                });
                
                tableHtml += '</table>';
                
                // Replace previous element with compiled table HTML
                lines[i] = tableHtml + '\n' + line;
                tableRows = [];
                inTable = false;
            }
        }
    }
    
    // Fallback: If table is still open at the end
    if (inTable && tableRows.length > 0) {
        let tableHtml = '<table class="console-table" style="border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 0.85rem; border: 1px solid rgba(255,255,255,0.08);">';
        tableRows.forEach((row, rowIdx) => {
            const isHeader = rowIdx === 0;
            tableHtml += `<tr style="${isHeader ? 'background: rgba(255,255,255,0.04);' : 'border-bottom: 1px solid rgba(255,255,255,0.05);'}">`;
            row.forEach(col => {
                const tag = isHeader ? 'th' : 'td';
                tableHtml += `<${tag} style="padding: 6px 10px; text-align: left; border: 1px solid rgba(255,255,255,0.06); font-weight: ${isHeader ? '600' : '400'}; color: ${isHeader ? 'var(--secondary)' : 'var(--text-primary)'};">${col}</${tag}>`;
            });
            tableHtml += '</tr>';
        });
        tableHtml += '</table>';
        lines.push(tableHtml);
    }
    
    // Filter and join lines using line breaks
    return lines.filter(l => l !== "").join('<br>');
}

// Render the detailed AI thought execution trace sequentially with typing delays
async function renderAgentTrace(trace) {
    elConsoleLogs.innerHTML = "";
    if (!trace || trace.length === 0) {
        elConsoleLogs.innerHTML = `<div class="console-welcome"><p class="console-prompt">> No traces returned.</p></div>`;
        return;
    }

    // Set UI indicator to active while typing trace steps
    document.querySelector(".status-dot").className = "status-dot yellow";
    document.querySelector(".status-text").textContent = "Agent Thinking";

    for (let stepIndex = 0; stepIndex < trace.length; stepIndex++) {
        const step = trace[stepIndex];
        const block = document.createElement("div");
        block.className = "trace-step";

        if (step.type === "assistant_thought") {
            block.innerHTML = `<div class="trace-thought"><span>[Agent Thought]</span><br><span class="type-content"></span></div>`;
            elConsoleLogs.appendChild(block);
            const contentSpan = block.querySelector(".type-content");
            await typeText(contentSpan, step.content, 4);
            contentSpan.innerHTML = parseMarkdown(step.content);
        } else if (step.type === "tool_call") {
            const argsStr = JSON.stringify(step.args, null, 2);
            block.innerHTML = `<div class="trace-call"><strong>[Call Tool]</strong> ${step.tool}<br>Arguments:<br><pre class="type-content" style="white-space: pre-wrap; font-family: inherit; margin: 4px 0 0 0;"></pre></div>`;
            elConsoleLogs.appendChild(block);
            const contentSpan = block.querySelector(".type-content");
            await typeText(contentSpan, argsStr, 8);
        } else if (step.type === "tool_result") {
            // Render a mini "Executing..." state for tool delay
            const executionLog = document.createElement("div");
            executionLog.className = "trace-step";
            executionLog.innerHTML = `<div class="trace-thought" style="opacity: 0.6;"><span>[System]</span> Running ${step.tool}...</div>`;
            elConsoleLogs.appendChild(executionLog);
            elConsoleLogs.scrollTop = elConsoleLogs.scrollHeight;
            
            await sleep(800);
            executionLog.remove();

            const resultStr = JSON.stringify(step.result, null, 2);
            block.innerHTML = `<div class="trace-result"><strong>[Tool Return]</strong> ${step.tool}<br><pre class="type-content" style="white-space: pre; font-family: inherit; margin: 4px 0 0 0;"></pre></div>`;
            elConsoleLogs.appendChild(block);
            const contentSpan = block.querySelector(".type-content");
            await typeText(contentSpan, resultStr, 4);
        } else if (step.type === "final_answer") {
            block.innerHTML = `<div class="trace-final"><strong>[Final Response]</strong><br><span class="type-content"></span></div>`;
            elConsoleLogs.appendChild(block);
            const contentSpan = block.querySelector(".type-content");
            await typeText(contentSpan, step.content, 4);
            contentSpan.innerHTML = parseMarkdown(step.content);
        } else if (step.type === "error") {
            block.innerHTML = `<div class="trace-thought" style="color: #f43f5e"><span>[Error]</span><br><span class="type-content"></span></div>`;
            elConsoleLogs.appendChild(block);
            const contentSpan = block.querySelector(".type-content");
            await typeText(contentSpan, step.content, 6);
        }
        
        elConsoleLogs.scrollTop = elConsoleLogs.scrollHeight;
        await sleep(350); // Small pause before printing the next logical step
    }

    document.querySelector(".status-dot").className = "status-dot green";
    document.querySelector(".status-text").textContent = "Agent Idle";
}

// Render Study Calendar Deck
function renderTimeline(state) {
    elTimelineDeck.innerHTML = "";
    const dayPlan = state.day_plan || {};
    const days = Object.keys(dayPlan);

    if (days.length === 0) {
        elTimelineDeck.innerHTML = `
            <div class="empty-timeline">
                <i class="fa-solid fa-calendar-xmark"></i>
                <p>No active study plan found.</p>
            </div>`;
        return;
    }

    // Sort days numerically
    days.sort((a, b) => {
        const numA = parseInt(a.replace(/^[^\d]*/, '')) || 0;
        const numB = parseInt(b.replace(/^[^\d]*/, '')) || 0;
        return numA - numB;
    });

    days.forEach(day => {
        const card = document.createElement("div");
        card.className = "study-card";

        // Day label details
        // Label format: "Day X (YYYY-MM-DD)"
        const match = day.match(/Day (\d+)\s*\((.*?)\)/);
        const dayNum = match ? `Day ${match[1]}` : day;
        const dayDate = match ? match[2] : "";

        // Status determinations
        let status = "pending";
        let statusText = "Pending";
        if (state.completed_days.includes(day)) {
            status = "completed";
            statusText = "Completed";
        } else if (state.missed_days.includes(day)) {
            status = "missed";
            statusText = "Missed";
        }

        card.classList.add(`status-${status}`);

        // Topics rendering
        const topics = dayPlan[day] || [];
        let topicsHtml = "";
        if (topics.includes("Missed")) {
            topicsHtml = `<span class="badge missed-badge" style="width: 100%; text-align: center; display: block; border-radius: 6px;"><i class="fa-solid fa-ban"></i> Day Missed</span>`;
        } else {
            topicsHtml = topics.map(topic => `<span class="topic-tag">${topic}</span>`).join(" ");
        }

        card.innerHTML = `
            <div class="card-header">
                <div>
                    <div class="card-day">${dayNum}</div>
                    <div class="card-date">${dayDate}</div>
                </div>
                <span class="card-status-badge ${status}">${statusText}</span>
            </div>
            <div class="card-topics">
                ${topicsHtml}
            </div>
        `;

        // Render card actions if pending
        if (status === "pending") {
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "card-actions";
            
            const btnComplete = document.createElement("button");
            btnComplete.className = "btn-complete-card";
            btnComplete.innerHTML = `<i class="fa-solid fa-circle-check"></i> Complete`;
            btnComplete.addEventListener("click", () => completeDay(day));

            const btnMiss = document.createElement("button");
            btnMiss.className = "btn-miss-card";
            btnMiss.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Missed`;
            btnMiss.addEventListener("click", () => missDay(day));

            actionsDiv.appendChild(btnComplete);
            actionsDiv.appendChild(btnMiss);
            card.appendChild(actionsDiv);
        }

        elTimelineDeck.appendChild(card);
    });
}

// Update schedule stats
function updateStatistics(state) {
    elSessionInfo.classList.remove("hidden");
    elTimelineSummary.classList.remove("hidden");

    elInfoExamDate.textContent = state.exam_date || "-";
    elInfoDaysLeft.textContent = state.days_left !== undefined ? state.days_left : "-";

    elCountCompleted.textContent = state.completed_days ? state.completed_days.length : 0;
    elCountMissed.textContent = state.missed_days ? state.missed_days.length : 0;
}

// Initialize on page load
loadSessionState();
