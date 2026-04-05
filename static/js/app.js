/* ═══════════════════════════════════════════════════════════
   Data Doctor — Frontend Logic
   ═══════════════════════════════════════════════════════════ */

let sessionId = null;
let reportData = null;

// ── File Upload ────────────────────────────────────────────

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
});

dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('drag-over');
});

dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
});


// ── Upload & Analysis Pipeline ─────────────────────────────

async function uploadFile(file) {
    showScreen('loading-screen');
    
    const steps = ['profiler', 'anomaly', 'feature', 'supervisor'];
    const messages = [
        'Profiling columns and distributions...',
        'Hunting for anomalies and outliers...',
        'Generating feature engineering ideas...',
        'Running supervisor QA audit...',
    ];

    // Animate steps sequentially
    for (let i = 0; i < steps.length; i++) {
        await delay(600);
        activateStep(steps[i], messages[i]);
        if (i > 0) completeStep(steps[i - 1]);
    }

    // Actually upload
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Analysis failed');
        }

        const data = await res.json();
        sessionId = data.session_id;
        reportData = data.report;

        completeStep('supervisor');
        await delay(500);
        
        showScreen('dashboard-screen');
        renderDashboard(data);

    } catch (err) {
        alert('Error: ' + err.message);
        showScreen('upload-screen');
    }
}

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function activateStep(stepName, msg) {
    const el = document.getElementById(`step-${stepName}`);
    el.classList.add('active');
    document.getElementById('loading-msg').textContent = msg;
}

function completeStep(stepName) {
    const el = document.getElementById(`step-${stepName}`);
    el.classList.remove('active');
    el.classList.add('done');
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }


// ── Dashboard Rendering ────────────────────────────────────

function renderDashboard(data) {
    const report = data.report;
    const charts = data.charts;

    // Animate health score
    animateHealthScore(report.health);

    // Priorities
    renderPriorities(report.health.top_priorities);

    // Tab bar
    document.getElementById('tab-bar').style.display = 'flex';
    setupTabs();

    // Charts
    renderCharts(charts);

    // Anomalies
    renderAnomalies(report.anomalies);

    // Features
    renderFeatures(report.features);

    // Columns table
    renderColumnsTable(report.profile);
}

function animateHealthScore(health) {
    const score = health.overall_score;
    const grade = health.overall_grade;
    const circumference = 2 * Math.PI * 52; // ~327

    // Animate ring
    const circle = document.getElementById('grade-circle');
    const offset = circumference - (score / 100) * circumference;

    // Color based on grade
    const gradeColors = { A: '#1D9E75', B: '#378ADD', C: '#EF9F27', D: '#D85A30', F: '#E24B4A' };
    const color = gradeColors[grade] || '#534AB7';
    circle.style.stroke = color;

    setTimeout(() => {
        circle.style.transition = 'stroke-dashoffset 1.8s cubic-bezier(0.22, 1, 0.36, 1)';
        circle.style.strokeDashoffset = offset;
    }, 200);

    // Animate number
    const scoreEl = document.getElementById('grade-score');
    const letterEl = document.getElementById('grade-letter');
    letterEl.style.color = color;
    animateNumber(scoreEl, 0, score, 1500, v => `${v}/100`);

    setTimeout(() => { letterEl.textContent = grade; }, 800);

    // Summary
    document.getElementById('health-summary').textContent = health.summary;

    // Score bars
    const bars = [
        { label: 'Completeness', score: health.completeness_score, color: '#1D9E75' },
        { label: 'Consistency', score: health.consistency_score, color: '#534AB7' },
        { label: 'Outlier score', score: health.outlier_score, color: '#378ADD' },
        { label: 'Feature readiness', score: health.feature_readiness_score, color: '#EF9F27' },
    ];

    const barsContainer = document.getElementById('score-bars');
    barsContainer.innerHTML = bars.map(b => `
        <div class="score-bar-item">
            <span class="score-bar-label">${b.label}</span>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="background:${b.color}" data-width="${b.score}%"></div>
            </div>
            <span class="score-bar-val">${b.score}</span>
        </div>
    `).join('');

    // Animate bars after a short delay
    setTimeout(() => {
        barsContainer.querySelectorAll('.score-bar-fill').forEach(fill => {
            fill.style.width = fill.dataset.width;
        });
    }, 400);
}

function animateNumber(el, from, to, duration, formatter) {
    const start = performance.now();
    function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(from + (to - from) * eased);
        el.textContent = formatter(current);
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function renderPriorities(priorities) {
    if (!priorities || priorities.length === 0) return;
    const section = document.getElementById('priorities-section');
    section.style.display = 'block';
    
    document.getElementById('priorities-list').innerHTML = priorities.map((p, i) => `
        <div class="priority-item" style="animation-delay: ${i * 0.1}s">
            <span class="priority-num">${i + 1}</span>
            <span>${p}</span>
        </div>
    `).join('');
}


// ── Tabs ───────────────────────────────────────────────────

function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');

            // Re-render Plotly charts when switching to charts tab (fixes sizing)
            if (tab.dataset.tab === 'charts') {
                document.querySelectorAll('.chart-card .plotly-chart').forEach(el => {
                    Plotly.Plots.resize(el);
                });
            }
        });
    });
}


// ── Charts ─────────────────────────────────────────────────

function renderCharts(charts) {
    const grid = document.getElementById('charts-grid');
    grid.innerHTML = '';

    const plotlyLayout = {
        paper_bgcolor: 'transparent',
        plot_bgcolor: 'transparent',
        font: { family: 'DM Sans, sans-serif', color: '#9896A8', size: 12 },
        margin: { t: 10, r: 20, b: 60, l: 50 },
        xaxis: { gridcolor: '#2A2A3C', zerolinecolor: '#2A2A3C' },
        yaxis: { gridcolor: '#2A2A3C', zerolinecolor: '#2A2A3C' },
        coloraxis: { colorbar: { tickfont: { color: '#9896A8' } } },
    };

    charts.forEach((chart, i) => {
        const card = document.createElement('div');
        card.className = 'chart-card';
        card.style.animationDelay = `${i * 0.1}s`;

        const title = document.createElement('div');
        title.className = 'chart-card-title';
        title.textContent = chart.title;
        card.appendChild(title);

        const plotDiv = document.createElement('div');
        plotDiv.className = 'plotly-chart';
        plotDiv.style.width = '100%';
        plotDiv.style.height = '320px';
        card.appendChild(plotDiv);

        grid.appendChild(card);

        const layout = { ...plotlyLayout, ...chart.layout };

        // Special layout for radar
        if (chart.type === 'radar' && chart.layout.polar) {
            layout.polar = {
                ...chart.layout.polar,
                bgcolor: 'transparent',
                radialaxis: {
                    ...chart.layout.polar.radialaxis,
                    gridcolor: '#2A2A3C',
                    linecolor: '#2A2A3C',
                    tickfont: { color: '#9896A8' },
                },
                angularaxis: {
                    gridcolor: '#2A2A3C',
                    linecolor: '#2A2A3C',
                    tickfont: { color: '#9896A8' },
                },
            };
        }

        Plotly.newPlot(plotDiv, chart.data, layout, {
            responsive: true,
            displayModeBar: false,
        });
    });
}


// ── Anomalies ──────────────────────────────────────────────

function renderAnomalies(anomalyReport) {
    const list = document.getElementById('anomaly-list');
    
    if (anomalyReport.anomalies.length === 0) {
        list.innerHTML = '<p style="color: var(--text2); padding: 24px;">No anomalies detected — your data looks clean!</p>';
        return;
    }

    // Sort: critical first
    const sorted = [...anomalyReport.anomalies].sort((a, b) => {
        const order = { critical: 0, warning: 1, info: 2 };
        return (order[a.severity] ?? 3) - (order[b.severity] ?? 3);
    });

    list.innerHTML = sorted.map((a, i) => `
        <div class="anomaly-card" style="animation-delay: ${i * 0.05}s">
            <span class="anomaly-badge ${a.severity}">${a.severity}</span>
            <div class="anomaly-body">
                <div class="anomaly-col">${a.column}</div>
                <div class="anomaly-desc">${a.description}</div>
                <div class="anomaly-rec">${a.recommendation}</div>
            </div>
        </div>
    `).join('');
}


// ── Features ───────────────────────────────────────────────

function renderFeatures(featureReport) {
    const list = document.getElementById('feature-list');

    if (featureReport.suggestions.length === 0) {
        list.innerHTML = '<p style="color: var(--text2); padding: 24px;">No feature suggestions — the dataset is well-prepared.</p>';
        return;
    }

    // Sort: high impact first
    const sorted = [...featureReport.suggestions].sort((a, b) => {
        const order = { high: 0, medium: 1, low: 2 };
        return (order[a.impact] ?? 3) - (order[b.impact] ?? 3);
    });

    list.innerHTML = sorted.map((f, i) => `
        <div class="feature-card" style="animation-delay: ${i * 0.05}s">
            <div class="feature-header">
                <span class="feature-col">${f.column}</span>
                <span class="feature-impact ${f.impact}">${f.impact}</span>
                <span style="font-size:11px; color:var(--text3); margin-left:auto">${f.suggestion_type}</span>
            </div>
            <div class="feature-desc">${f.description}</div>
            <div class="feature-code">${escapeHtml(f.code_snippet)}</div>
            <div class="feature-rationale">${f.rationale}</div>
        </div>
    `).join('');
}


// ── Columns Table ──────────────────────────────────────────

function renderColumnsTable(profile) {
    const wrap = document.getElementById('columns-table-wrap');
    
    const rows = profile.columns.map(c => `
        <tr>
            <td style="font-family:var(--mono); font-weight:500">${c.name}</td>
            <td><span class="type-badge ${c.semantic_type}">${c.semantic_type}</span></td>
            <td>${c.dtype}</td>
            <td class="missing-indicator" style="color: ${c.missing_pct > 15 ? 'var(--red)' : c.missing_pct > 5 ? 'var(--amber)' : 'var(--teal)'}">${c.missing_pct}%</td>
            <td>${c.unique_count.toLocaleString()}</td>
            <td style="font-family:var(--mono); font-size:12px">${c.mean !== null ? c.mean : '—'}</td>
            <td style="font-family:var(--mono); font-size:12px">${c.std !== null ? c.std : '—'}</td>
        </tr>
    `).join('');

    wrap.innerHTML = `
        <table class="columns-table">
            <thead>
                <tr>
                    <th>Column</th>
                    <th>Type</th>
                    <th>Dtype</th>
                    <th>Missing</th>
                    <th>Unique</th>
                    <th>Mean</th>
                    <th>Std</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}


// ── Chat ───────────────────────────────────────────────────

function toggleChat() {
    const panel = document.getElementById('chat-panel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        document.getElementById('chat-input').focus();
    }
}

async function sendChat() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg || !sessionId) return;

    input.value = '';
    appendMessage('user', msg);

    // Show typing indicator
    const typingId = appendMessage('bot', '<span class="typing">Thinking...</span>');

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, session_id: sessionId }),
        });

        const data = await res.json();
        removeMessage(typingId);
        appendMessage('bot', formatMarkdown(data.reply));

    } catch (err) {
        removeMessage(typingId);
        appendMessage('bot', 'Sorry, something went wrong. Please try again.');
    }
}

function appendMessage(role, html) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    const id = 'msg-' + Date.now();
    div.className = `msg ${role}`;
    div.id = id;
    div.innerHTML = role === 'user' ? escapeHtml(html) : html;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function formatMarkdown(text) {
    // Basic markdown: code blocks, inline code, bold, newlines
    return text
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre style="background:var(--bg);padding:10px;border-radius:8px;overflow-x:auto;font-size:12px;margin:8px 0;border:1px solid var(--border)"><code>$2</code></pre>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
