// static/app.js
let socket;
let clientsList = [];
let totalChart, clientChart;

function initCharts() {
  const ctxT = document.getElementById('totalTrafficChart').getContext('2d');
  totalChart = new Chart(ctxT, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Bytes In', data: [] }, { label: 'Bytes Out', data: [] }] },
    options: { responsive: true }
  });

  const ctxC = document.getElementById('clientChart').getContext('2d');
  clientChart = new Chart(ctxC, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Bytes In', data: [] }, { label: 'Bytes Out', data: [] }] },
    options: { responsive: true }
  });
}

function populateClients(clients) {
  const tbody = document.getElementById('clientTable');
  tbody.innerHTML = "";
  const select = document.getElementById('clientSelect');
  select.innerHTML = "<option value=''>-- choose client --</option>";
  clients.forEach(c => {
    clientsList.push(c.name);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="p-2">
        <div class="${!c.connected ? 'text-red-400' : ''}">
          <div class="font-semibold">${c.name}</div>
          <div class="text-xs text-gray-400">
            ${c.remote_ip} → ${c.virtual_ip}
          </div>
        </div>
      </td>
      <td class="p-2">${c.remote_ip}</td>
      <td class="p-2">${c.virtual_ip}</td>
      <td class="p-2 text-sm">
        <span class="text-blue-400">↓ ${c.bytes_received || '0'}</span><br>
        <span class="text-red-400">↑ ${c.bytes_sent || '0'}</span>
      </td>
      <td class="p-2 ${c.connected ? 'text-green-400' : 'text-red-400'}">${c.last_seen}</td>
      <td class="p-2 text-right space-x-1">
        <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="showQR('${c.name}')">QR</button>
        <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="showConfig('${c.name}')">View</button>
        <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="downloadConfig('${c.name}')">⬇</button>
        <button class="px-2 py-1 bg-gray-600 rounded text-red-400 hover:bg-gray-700" onclick="deleteConfig('${c.name}')">🗑</button>
      </td>
    `;
    tbody.appendChild(tr);

    const opt = document.createElement('option');
    opt.value = c.name;
    opt.text = c.name;
    select.appendChild(opt);
  });
}

function connectWS() {
  socket = new WebSocket(((location.protocol === 'https:') ? 'wss://' : 'ws://') + window.location.host + '/ws/clients');

  socket.onopen = () => console.log('WS open');
  socket.onclose = () => setTimeout(connectWS, 3000);
  socket.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    document.getElementById('totalClients').textContent = data.total;
    document.getElementById('connectedClients').textContent = data.connected;
    // re-render client list
    populateClients(data.list);
    // optionally update total traffic chart (aggregate)
    // For simplicity, we won't aggregate here; you can fetch /api/traffic for totals.
  };
}

async function loadHistory(name) {
  const res = await fetch(`/api/traffic/${name}?hours=24`);
  const json = await res.json();
  const rows = json.rows;
  const labels = rows.map(r => r.ts);
  const bytesIn = rows.map(r => r.bytes_in);
  const bytesOut = rows.map(r => r.bytes_out);
  clientChart.data.labels = labels;
  clientChart.data.datasets[0].data = bytesIn;
  clientChart.data.datasets[1].data = bytesOut;
  clientChart.update();
}

window.addEventListener('load', () => {
  initCharts();
  connectWS();
  document.getElementById('clientSelect').addEventListener('change', (e) => {
    if (e.target.value) loadHistory(e.target.value);
  });
});


async function toggleConfig(name, enable) {
  const formData = new FormData();
  formData.append("enable", enable);
  const res = await fetch(`/api/config/${name}/toggle`, {
    method: "POST",
    body: formData,
  });
  const json = await res.json();
  if (json.ok) alert(`${enable ? "Enabled" : "Disabled"} ${name}`);
}

async function refreshClients() {
    try {
      const res = await fetch('/api/clients');
      const data = await res.json();

      document.getElementById("totalClients").textContent = data.total;
      document.getElementById("connectedClients").textContent = data.connected.length;

      const table = document.getElementById("clientTable");
      table.innerHTML = "";

      data.clients.forEach(c => {
        const isActive = c.connected === true;
        const tr = document.createElement("tr");
        if (!isActive) {
          tr.classList.add("opacity-50");
        }
        tr.innerHTML = `
        <td class="p-2">
          <div class="${isActive ? '' : 'text-red-400'}">
            <div class="font-semibold">${c.name}</div>
            <div class="text-xs text-gray-400">${c.remote_ip} → ${c.virtual_ip}</div>
          </div>
        </td>
        <td class="p-2">${c.remote_ip}</td>
        <td class="p-2">${c.virtual_ip}</td>
        <td class="p-2 text-sm">
          <span class="text-blue-400">↓ ${c.bytes_received || '0'}</span><br>
          <span class="text-red-400">↑ ${c.bytes_sent || '0'}</span>
        </td>
        <td class="p-2 ${isActive ? 'text-green-400' : 'text-red-400'}">${c.last_seen}</td>
        <td class="p-2 text-right space-x-1">
          <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="showQR('${c.name}')">QR</button>
          <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="showConfig('${c.name}')">View</button>
          <button class="px-2 py-1 bg-gray-600 rounded hover:bg-gray-500" onclick="downloadConfig('${c.name}')">⬇</button>
          <button class="px-2 py-1 bg-gray-600 rounded text-red-400 hover:bg-gray-700" onclick="deleteConfig('${c.name}')">🗑</button>
        </td>
      `;
    table.appendChild(tr);
  });
    } catch (err) {
      console.error("Failed to update clients:", err);
    }
  }

async function showQR(name) {
  const img = document.getElementById("qrImage");
  img.src = `/api/client/${name}/qr?${Date.now()}`;  // cache-bust
  document.getElementById("qrOverlay").classList.remove("hidden");
  document.getElementById("qrOverlay").classList.add("flex");
}

function hideQR() {
  document.getElementById("qrOverlay").classList.add("hidden");
  document.getElementById("qrOverlay").classList.remove("flex");
  document.getElementById("qrImage").src = ""; 
}


async function showConfig(name) {
  document.getElementById("configName").innerText = name;
  const res = await fetch(`/api/config/${name}`);
  if (!res.ok) {
    alert("Config not found.");
    return;
  }
  const text = await res.text();
  document.getElementById("configText").innerText = text;
  document.getElementById("configOverlay").classList.remove("hidden");
  document.getElementById("configOverlay").classList.add("flex");
}

function hideConfig() {
  document.getElementById("configOverlay").classList.add("hidden");
  document.getElementById("configOverlay").classList.remove("flex");
  document.getElementById("configText").innerText = "";
}

function downloadConfig(name) {
  window.open(`/api/config/${name}/download`, "_blank");
}

async function deleteConfig(name) {
  if (!confirm(`Delete config ${name}?`)) return;
  const res = await fetch(`/api/config/${name}`, { method: "DELETE" });
  const json = await res.json();
  if (json.deleted) {
    alert("Deleted successfully!");
    refreshClients();
  } else alert("Failed to delete config.");
}

// Refresh periodically
refreshClients();
setInterval(refreshClients, 10000);
