/**
 * Instructor Dashboard Controller
 * Displays candidate metrics, integrity scores, and audit trail with photo evidence.
 */

let allSubmissions = [];

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();

    document.getElementById('searchInput').addEventListener('input', (e) => {
        filterTable(e.target.value);
    });

    document.getElementById('closeModalBtn').addEventListener('click', () => {
        document.getElementById('auditModal').classList.remove('active');
    });

    // Close modal when clicking on overlay background
    document.getElementById('auditModal').addEventListener('click', (e) => {
        if (e.target.id === 'auditModal') {
            document.getElementById('auditModal').classList.remove('active');
        }
    });
});

async function loadDashboardData() {
    try {
        const res = await fetch('/api/dashboard-data');
        const data = await res.json();

        if (data.success) {
            updateMetrics(data.metrics);
            allSubmissions = data.submissions;
            renderSubmissionsTable(allSubmissions);
        }
    } catch (err) {
        console.error("Failed to load dashboard data:", err);
    }
}

function updateMetrics(metrics) {
    document.getElementById('metricTotalStudents').innerText = metrics.total_students;
    document.getElementById('metricAvgScore').innerText = `${metrics.avg_score} / 50`;
    document.getElementById('metricAvgIntegrity').innerText = `${metrics.avg_integrity}%`;
    document.getElementById('metricFlagged').innerText = metrics.flagged_sessions;
}

function renderSubmissionsTable(submissions) {
    const tbody = document.getElementById('submissionsBody');
    tbody.innerHTML = '';

    if (!submissions || submissions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem; color: #94a3b8;">No candidate submissions recorded yet.</td></tr>`;
        return;
    }

    submissions.forEach(sub => {
        const tr = document.createElement('tr');

        // Integrity Meter Color
        let meterClass = 'meter-high';
        let badgeClass = 'badge-trust';
        let riskLabel = 'Verified';

        if (sub.integrity_score < 65) {
            meterClass = 'meter-low';
            badgeClass = 'badge-flagged';
            riskLabel = 'High Risk';
        } else if (sub.integrity_score < 85) {
            meterClass = 'meter-med';
            badgeClass = 'badge-suspicious';
            riskLabel = 'Suspicious';
        }

        tr.innerHTML = `
            <td>
                <strong>${sub.roll_no}</strong>
                <div style="font-size: 0.8rem; color: #94a3b8;">${sub.student_name}</div>
            </td>
            <td>${sub.exam_title || 'CSE Core Exam'}</td>
            <td><strong>${sub.score}</strong> / ${sub.total_marks || 50}</td>
            <td>
                <div class="integrity-meter">
                    <div class="meter-track">
                        <div class="meter-fill ${meterClass}" style="width: ${sub.integrity_score}%;"></div>
                    </div>
                    <span style="font-weight: 700;">${sub.integrity_score}%</span>
                </div>
            </td>
            <td><strong style="color: ${sub.violations_count > 0 ? '#f87171' : '#34d399'}">${sub.violations_count}</strong></td>
            <td><span class="dash-badge ${badgeClass}">${riskLabel}</span></td>
            <td>
                <button class="btn-inspect" onclick="openAuditModal(${sub.id}, '${sub.student_name}', '${sub.roll_no}')">
                    Inspect Logs
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterTable(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    const filtered = allSubmissions.filter(s => 
        s.roll_no.toLowerCase().includes(term) ||
        s.student_name.toLowerCase().includes(term)
    );
    renderSubmissionsTable(filtered);
}

async function openAuditModal(submissionId, name, rollNo) {
    const modal = document.getElementById('auditModal');
    const modalTitle = document.getElementById('modalCandidateInfo');
    const timelineContainer = document.getElementById('auditTimeline');

    modalTitle.innerText = `${name} (${rollNo}) — Audit Logs`;
    timelineContainer.innerHTML = '<p style="color: #94a3b8;">Loading audit trail...</p>';
    modal.classList.add('active');

    try {
        const res = await fetch(`/api/submission/${submissionId}/violations`);
        const data = await res.json();

        timelineContainer.innerHTML = '';

        if (!data.violations || data.violations.length === 0) {
            timelineContainer.innerHTML = `
                <div style="padding: 1.5rem; text-align: center; color: #34d399; font-weight: 600;">
                    ✓ Clean Session: No integrity violations detected during this examination.
                </div>
            `;
            return;
        }

        data.violations.forEach(v => {
            const item = document.createElement('div');
            item.className = 'timeline-item';

            let snapshotHtml = '';
            if (v.snapshot_filename) {
                snapshotHtml = `
                    <div style="margin-top: 0.5rem;">
                        <a href="/uploads/${v.snapshot_filename}" target="_blank" title="Click to view full photo">
                            <img src="/uploads/${v.snapshot_filename}" class="snapshot-thumb" alt="Violation snapshot">
                        </a>
                    </div>
                `;
            }

            item.innerHTML = `
                <div class="timeline-time">${v.timestamp}</div>
                <div class="timeline-type">${v.violation_type.replace('_', ' ')}</div>
                <div class="timeline-desc">${v.description}</div>
                ${snapshotHtml}
            `;
            timelineContainer.appendChild(item);
        });
    } catch (err) {
        timelineContainer.innerHTML = '<p style="color: #ef4444;">Failed to load violation records.</p>';
    }
}
