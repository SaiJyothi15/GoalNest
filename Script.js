// static/script.js

// --- Helpers ---
function showNotification(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification(title, { body });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission().then(p => {
      if (p === "granted") new Notification(title, { body });
    });
  }
}

async function getJSON(url) {
  const res = await fetch(url);
  return res.json();
}
async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
}
async function deleteJSON(url, payload) {
  const res = await fetch(url, {
    method: "DELETE",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });
  return res.json();
}

// --- Streak & Stats ---
async function refreshStreak() {
  const data = await getJSON('/streak');
  document.getElementById('streakCount').innerText = data.streak || 0;
  document.getElementById('longestCount').innerText = data.longest || 0;
}
let chart;
async function renderChart() {
  const { labels, data } = await getJSON('/stats/daily');
  const ctx = document.getElementById('streakChart').getContext('2d');
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Daily Completions',
        data,
        borderWidth: 2,
        pointRadius: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }},
      scales: {
        x: { ticks: { maxTicksLimit: 7 } },
        y: { beginAtZero: true, ticks: { precision: 0, stepSize: 1, max: Math.max(3, Math.max(...data, 0)) } }
      }
    }
  });
}

// --- Tasks ---
async function fetchTasks() {
  const tasks = await getJSON('/tasks');
  const ul = document.getElementById('taskList');
  ul.innerHTML = '';
  const today = new Date().toISOString().slice(0,10);

  tasks.forEach(t => {
    const li = document.createElement('li');
    li.className = 'task';
    if (t.completed) li.classList.add('done');

    const left = document.createElement('div');
    left.className = 'task-left';
    left.innerHTML = `
      <span class="chip ${t.category.toLowerCase()}">${t.category}</span>
      <span class="task-title">${t.task}</span>
      <span class="task-time">@ ${t.time || '--:--'}</span>
    `;

    const actions = document.createElement('div');
    actions.className = 'task-actions';

    const btnDone = document.createElement('button');
    btnDone.className = 'icon success';
    btnDone.title = 'Mark complete';
    btnDone.innerText = '✔';
    btnDone.disabled = !!t.completed;
    btnDone.onclick = async () => {
      await postJSON('/complete', { id: t.id });
      await fetchTasks();
      await refreshStreak();
      await renderChart();
      showNotification("Task complete", "Nice! Your streak may have increased.");
    };

    const btnDelete = document.createElement('button');
    btnDelete.className = 'icon danger';
    btnDelete.title = 'Delete';
    btnDelete.innerText = '✖';
    btnDelete.onclick = async () => {
      await deleteJSON('/tasks', { id: t.id });
      await fetchTasks();
      await renderChart();
    };

    actions.appendChild(btnDone);
    actions.appendChild(btnDelete);

    li.appendChild(left);
    li.appendChild(actions);
    ul.appendChild(li);
  });

  // schedule a nightly reminder (after 20:00 local) if no completed task today
  tryNightlyReminder(tasks);
}

function tryNightlyReminder(tasks) {
  // If after 20:00 and user has no completed task today, show a reminder notification
  const now = new Date();
  const hour = now.getHours();
  const todayPrefix = now.toISOString().slice(0,10);
  const completedToday = tasks.some(t => t.completed && (t.completed_at || '').startsWith(todayPrefix));
  if (hour >= 20 && !completedToday) {
    showNotification("Keep your streak alive 🔥", "You have pending tasks today. Complete one to avoid reset!");
  }
}

// --- Add Task form ---
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('addForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const task = document.getElementById('taskInput').value.trim();
      const category = document.getElementById('catSelect').value;
      const time = document.getElementById('timeInput').value;
      if (!task) return;
      await postJSON('/tasks', { task, category, time });
      document.getElementById('taskInput').value = '';
      await fetchTasks();
      await renderChart();
    });
  }

  // Tips & Quotes
  document.getElementById('tipBtn')?.addEventListener('click', async () => {
    const data = await getJSON('/recommendation');
    document.getElementById('tipText').innerText = data.tip;
  });

  document.getElementById('quoteBtn')?.addEventListener('click', async () => {
    const data = await getJSON('/quote');
    document.getElementById('quoteText').innerText = `"${data.quote}"`;
  });

  // Initial load
  Notification?.requestPermission?.();
  refreshStreak();
  fetchTasks();
  renderChart();
});
