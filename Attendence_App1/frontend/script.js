// Attendance App Script v4.0
const API_URL = window.location.origin;
const EMPLOYEE_ID = 'EL220667'; // Constant for this demo

// DOM Elements
const mainBtn = document.getElementById('main-action-btn');
const actionText = document.getElementById('action-text');
const actionIcon = document.getElementById('action-icon');
const checkInDisplay = document.getElementById('check-in-time');
const checkOutDisplay = document.getElementById('check-out-time');
const effectiveHoursDisplay = document.getElementById('effective-hours');
const breakBtn = document.getElementById('break-btn');
const video = document.getElementById('video');
const cameraContainer = document.getElementById('camera-container');
const liveClockDisplay = document.getElementById('live-clock');
const cameraOverlay = document.getElementById('camera-overlay');
const hoursLabel = document.getElementById('hours-label');
const resetLink = document.getElementById('reset-link');
const navHome = document.getElementById('nav-home');
const navAttendance = document.getElementById('nav-attendance');
const homeView = document.getElementById('home-view');
const attendanceView = document.getElementById('attendance-view');

let currentStatus = 'checked_out';
let checkInTime = null;
let breakStartTime = null;
let totalBreakSeconds = 0;
let timerInterval = null;
let breakTimerInterval = null;

// Initialize UI
async function init() {
    // Initial Zero State for Fresh Start
    resetUItoZero();
    updateDate();
    updateLiveClock();

    // Automatic Reset on Refresh as requested
    try {
        await fetch(`${API_URL}/reset?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });
    } catch (e) {
        console.error('Initial reset failed', e);
    }

    await fetchStatus();
    setupNav();
    setInterval(updateDate, 60000); // Update date every minute
    setInterval(updateLiveClock, 1000); // Update clock every second
    setInterval(fetchStatus, 10000); // Poll status every 10 seconds for alerts
}

function updateLiveClock() {
    const now = new Date();
    liveClockDisplay.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

function updateDate() {
    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    document.getElementById('current-date').innerText = new Date().toLocaleDateString('en-US', options);
}

async function fetchStatus() {
    try {
        const response = await fetch(`${API_URL}/status/${EMPLOYEE_ID}`);
        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateUI(data) {
    currentStatus = data.status || 'checked_out';
    checkInTime = data.check_in ? new Date(data.check_in.replace(' ', 'T')) : null;
    breakStartTime = data.break_start ? new Date(data.break_start.replace(' ', 'T')) : null;
    totalBreakSeconds = data.total_break_seconds || 0;

    // Update times
    const inTime = data.check_in ? formatTime(data.check_in) : '--:--';
    const outTime = data.check_out ? formatTime(data.check_out) : '--:--';
    checkInDisplay.innerText = inTime;
    checkOutDisplay.innerText = outTime;

    // Update Nav times
    document.getElementById('nav-in').innerText = `In: ${inTime}`;
    document.getElementById('nav-out').innerText = `Out: ${outTime}`;

    console.log("Status Data:", data);
    console.log("Check-in Time:", checkInTime);

    // Update main button state
    mainBtn.classList.remove('check-in', 'check-out', 'hidden');
    breakBtn.classList.remove('btn-green', 'btn-red', 'hidden');

    if (currentStatus === 'checked_in') {
        hoursLabel.innerText = 'Effective Hours:';
        actionText.innerText = 'Clock Out';
        actionIcon.className = 'fas fa-sign-out-alt';
        mainBtn.classList.add('check-out');
        breakBtn.innerText = 'Take a Break';
        breakBtn.classList.add('btn-green');
        breakBtn.disabled = false;
        startLiveTimer();
        stopBreakTimer();
    } else if (currentStatus === 'on_break') {
        hoursLabel.innerText = 'Current Break:';
        actionText.innerText = 'End Break';
        actionIcon.className = 'fas fa-coffee';
        mainBtn.classList.add('check-out'); // Keep red look
        breakBtn.innerText = 'Resume Work';
        breakBtn.classList.add('btn-red');
        breakBtn.disabled = false;
        stopLiveTimer();
        startBreakTimer();
    } else {
        hoursLabel.innerText = 'Effective Hours:';
        actionText.innerText = 'Clock In';
        actionIcon.className = 'fas fa-fingerprint';
        mainBtn.classList.add('check-in');
        breakBtn.disabled = true;
        stopLiveTimer();
        stopBreakTimer();
    }

    // Update Attendance Tab Details
    document.getElementById('det-in').innerText = data.check_in ? formatTimeWithSeconds(data.check_in) : '--:--:--';
    document.getElementById('det-out').innerText = data.check_out ? formatTimeWithSeconds(data.check_out) : '--:--:--';

    // Render Breaks List
    const breaksList = document.getElementById('breaks-list');
    if (data.breaks && data.breaks.length > 0) {
        breaksList.innerHTML = data.breaks.map((b, index) => `
            <div class="break-row">
                <label>Break #${index + 1}</label>
                <span>${formatTimeWithSeconds(b.start_time)} - ${b.end_time ? formatTimeWithSeconds(b.end_time) : '...'}</span>
            </div>
        `).join('');
    } else {
        breaksList.innerHTML = '<div class="no-breaks">No breaks taken yet</div>';
    }

    document.getElementById('det-total-break').innerText = formatDuration(data.total_break_seconds / 3600);

    // Calculate and show total stay duration
    if (checkInTime && !isNaN(checkInTime.getTime())) {
        const endTime = data.check_out ? new Date(data.check_out.replace(' ', 'T')) : new Date();
        const totalDurationHours = (endTime - checkInTime) / 3600000;
        document.getElementById('det-total-stay').innerText = formatDuration(totalDurationHours);
    } else {
        document.getElementById('det-total-stay').innerText = '00:00:00';
    }

    const effectiveStr = data.effective_hours !== undefined ? formatDuration(data.effective_hours) : '00:00:00';
    const totalStr = document.getElementById('det-total-stay').innerText;
    const breakStr = document.getElementById('det-total-break').innerText;

    document.getElementById('det-effective').innerHTML = `${effectiveStr} <small style="font-size: 10px; opacity: 0.6; font-weight: normal; margin-left: 5px;">(${totalStr} + ${breakStr})</small>`;

    // Handle Alerts
    const alertBanner = document.getElementById('break-alert-banner');
    if (data.status === 'on_break' && data.breaks && data.breaks.length > 0) {
        const currentBreak = data.breaks[data.breaks.length - 1];
        if (currentBreak.alert_sent_1h) {
            alertBanner.innerText = "🛑 WARNING: Break exceeded 1 hour! Warning email has been sent.";
            alertBanner.className = "alert-banner alert-warning";
            alertBanner.classList.remove('hidden');
        } else if (currentBreak.alert_sent_30m) {
            alertBanner.innerText = "⚠️ REMINDER: You have used more than 1 minute of break! Reminder email sent.";
            alertBanner.className = "alert-banner alert-reminder";
            alertBanner.classList.remove('hidden');
        } else {
            alertBanner.classList.add('hidden');
        }
    } else {
        alertBanner.classList.add('hidden');
    }
}

function resetUItoZero() {
    document.getElementById('effective-hours').innerHTML = `00:00:00 <span class="info-icon">i</span>`;
    document.getElementById('det-in').innerText = '--:--:--';
    document.getElementById('det-out').innerText = '--:--:--';
    document.getElementById('det-total-stay').innerText = '00:00:00';
    document.getElementById('det-total-break').innerText = '00:00:00';
    document.getElementById('det-effective').innerText = '00:00:00';
    document.getElementById('breaks-list').innerHTML = '<div class="no-breaks">No breaks taken yet</div>';
    document.getElementById('nav-in').innerText = 'In: --:--';
    document.getElementById('nav-out').innerText = 'Out: --:--';
}

function startLiveTimer() {
    if (timerInterval) clearInterval(timerInterval);
    updateEffectiveHours(); // Initial call
    timerInterval = setInterval(updateEffectiveHours, 1000);
}

function stopLiveTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function startBreakTimer() {
    if (breakTimerInterval) clearInterval(breakTimerInterval);
    updateBreakDisplay(); // Initial call
    breakTimerInterval = setInterval(updateBreakDisplay, 1000);
}

function stopBreakTimer() {
    if (breakTimerInterval) {
        clearInterval(breakTimerInterval);
        breakTimerInterval = null;
    }
}

function updateBreakDisplay() {
    if (!breakStartTime || isNaN(breakStartTime.getTime())) return;
    const now = new Date();
    const breakSeconds = (now - breakStartTime) / 1000;
    const hours = Math.max(0, breakSeconds / 3600);
    effectiveHoursDisplay.innerHTML = `${formatDuration(hours)} <span class="info-icon">i</span>`;

    // Live alert monitoring
    const alertBanner = document.getElementById('break-alert-banner');
    if (breakSeconds > 3600) {
        alertBanner.innerText = "🛑 WARNING: Break exceeded 1 hour! Warning email being triggered...";
        alertBanner.className = "alert-banner alert-warning";
        alertBanner.classList.remove('hidden');
    } else if (breakSeconds > 60) {
        alertBanner.innerText = "⚠️ REMINDER: You have used more than 1 minute of break! Reminder email sent.";
        alertBanner.className = "alert-banner alert-reminder";
        alertBanner.classList.remove('hidden');
    }
}

function updateEffectiveHours() {
    if (!checkInTime || isNaN(checkInTime.getTime())) return;

    const now = new Date();
    const totalSecondsAtWork = (now - checkInTime) / 1000;
    const effectiveSeconds = totalSecondsAtWork + totalBreakSeconds; // Changed to + as requested
    const hours = Math.max(0, effectiveSeconds / 3600);

    effectiveHoursDisplay.innerHTML = `${formatDuration(hours)} <span class="info-icon">i</span>`;

    // Also update total stay in attendance tab if visible
    const totalStayHours = totalSecondsAtWork / 3600;
    const detTotalStay = document.getElementById('det-total-stay');
    if (detTotalStay) detTotalStay.innerText = formatDuration(totalStayHours);

    const detEffective = document.getElementById('det-effective');
    if (detEffective) {
        detEffective.innerHTML = `${formatDuration(hours)} <small style="font-size: 10px; opacity: 0.6; font-weight: normal; margin-left: 5px;">(${formatDuration(totalStayHours)} + ${formatDuration(totalBreakSeconds / 3600)})</small>`;
    }
}

function formatTime(dateTimeStr) {
    if (!dateTimeStr) return '--:--';
    try {
        const date = new Date(dateTimeStr.replace(' ', 'T'));
        if (isNaN(date.getTime())) return '--:--';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
    } catch (e) {
        return '--:--';
    }
}

function formatTimeWithSeconds(dateTimeStr) {
    if (!dateTimeStr) return '--:--:--';
    try {
        const date = new Date(dateTimeStr.replace(' ', 'T'));
        if (isNaN(date.getTime())) return '--:--:--';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch (e) {
        return '--:--:--';
    }
}

function formatDuration(hours) {
    const totalSeconds = Math.round(hours * 3600);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Navigation
function setupNav() {
    navHome.addEventListener('click', () => switchTab('home'));
    navAttendance.addEventListener('click', () => switchTab('attendance'));
    resetLink.addEventListener('click', (e) => {
        e.preventDefault();
        if (confirm('This will delete today\'s attendance data. Are you sure?')) {
            handleReset();
        }
    });
}

function switchTab(tab) {
    navHome.classList.remove('active');
    navAttendance.classList.remove('active');
    homeView.classList.add('hidden');
    attendanceView.classList.add('hidden');

    if (tab === 'home') {
        navHome.classList.add('active');
        homeView.classList.remove('hidden');
    } else {
        navHome.classList.add('active'); // Keep indicator or change logic
        navAttendance.classList.add('active');
        attendanceView.classList.remove('hidden');
    }
}

// Action Handlers
mainBtn.addEventListener('click', async () => {
    if (currentStatus === 'checked_out') {
        await handleCheckIn();
    } else if (currentStatus === 'checked_in') {
        await handleCheckOut();
    } else if (currentStatus === 'on_break') {
        await handleBreakEnd();
    }
});

breakBtn.addEventListener('click', async () => {
    if (currentStatus === 'checked_in') {
        await handleBreakStart();
    } else if (currentStatus === 'on_break') {
        await handleBreakEnd();
    }
});

async function handleCheckIn() {
    // Show camera preview for "face recognition"
    await startCamera();
    mainBtn.classList.add('hidden'); // Hide button to show face
    cameraOverlay.innerText = 'Recognizing...';
    cameraOverlay.classList.remove('hidden', 'success');

    // Simulate processing
    setTimeout(async () => {
        try {
            cameraOverlay.innerText = 'OK!';
            cameraOverlay.classList.add('success');

            const response = await fetch(`${API_URL}/check-in?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Server error');
            }

            const data = await response.json();

            setTimeout(() => {
                stopCamera();
                cameraOverlay.classList.add('hidden');
                updateUI(data);
            }, 1000);
        } catch (error) {
            alert('Failed to check in: ' + error.message);
            stopCamera();
            mainBtn.classList.remove('hidden');
        }
    }, 2000);
}

async function handleCheckOut() {
    await startCamera();
    mainBtn.classList.add('hidden');
    cameraOverlay.innerText = 'Recognizing...';
    cameraOverlay.classList.remove('hidden', 'success');

    setTimeout(async () => {
        try {
            cameraOverlay.innerText = 'OK!';
            cameraOverlay.classList.add('success');

            const response = await fetch(`${API_URL}/check-out?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Server error');
            }
            const data = await response.json();

            setTimeout(() => {
                stopCamera();
                cameraOverlay.classList.add('hidden');
                updateUI(data);
            }, 1000);
        } catch (error) {
            alert('Failed to check out: ' + error.message);
            stopCamera();
            mainBtn.classList.remove('hidden');
        }
    }, 2000);
}

async function handleBreakStart() {
    await startCamera();
    mainBtn.classList.add('hidden');
    breakBtn.classList.add('hidden'); // Hide break button too
    cameraOverlay.innerText = 'Recognizing...';
    cameraOverlay.classList.remove('hidden', 'success');

    setTimeout(async () => {
        try {
            cameraOverlay.innerText = 'OK!';
            cameraOverlay.classList.add('success');

            const response = await fetch(`${API_URL}/break-start?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Server error');
            }
            const data = await response.json();

            setTimeout(() => {
                stopCamera();
                cameraOverlay.classList.add('hidden');
                updateUI(data);
            }, 1000);
        } catch (error) {
            alert('Failed to start break: ' + error.message);
            stopCamera();
            mainBtn.classList.remove('hidden');
            breakBtn.classList.remove('hidden');
        }
    }, 2000);
}

async function handleBreakEnd() {
    await startCamera();
    mainBtn.classList.add('hidden');
    breakBtn.classList.add('hidden');
    cameraOverlay.innerText = 'Recognizing...';
    cameraOverlay.classList.remove('hidden', 'success');

    setTimeout(async () => {
        try {
            cameraOverlay.innerText = 'OK!';
            cameraOverlay.classList.add('success');

            const response = await fetch(`${API_URL}/break-end?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Server error');
            }
            const data = await response.json();

            setTimeout(() => {
                stopCamera();
                cameraOverlay.classList.add('hidden');
                updateUI(data);
            }, 1000);
        } catch (error) {
            alert('Failed to end break: ' + error.message);
            stopCamera();
            mainBtn.classList.remove('hidden');
            breakBtn.classList.remove('hidden');
        }
    }, 2000);
}

async function handleReset() {
    try {
        const response = await fetch(`${API_URL}/reset?employee_id=${EMPLOYEE_ID}`, { method: 'POST' });
        if (response.ok) {
            window.location.reload();
        }
    } catch (error) {
        alert('Failed to reset: ' + error.message);
    }
}

// Camera Handling
async function startCamera() {
    cameraContainer.classList.remove('hidden');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
    } catch (err) {
        console.error("Camera access denied:", err);
    }
}

function stopCamera() {
    const stream = video.srcObject;
    if (stream) {
        const tracks = stream.getTracks();
        tracks.forEach(track => track.stop());
    }
    cameraContainer.classList.add('hidden');
}

async function handleTestEmail() {
    try {
        const res = await fetch(`${API_URL}/test-email?email=madasuvenky263@gmail.com`);
        const data = await res.json();
        alert(data.message);
    } catch (err) {
        console.error("Test email failed:", err);
        alert("Failed to trigger test email. Check console.");
    }
}

// Start
init();
