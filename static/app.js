let socket;
let clientsList = [];

function populateClients(clients) {
  const tbody = document.getElementById('clientTable');
  tbody.innerHTML = "";
  const select = document.getElementById('clientSelect');
  select.innerHTML = "<option value=''>-- choose client --</option>";
  clients.forEach(c => {
    clientsList.push(c.name);
    const tr = document.createElement('tr');
    if (!c.connected) {
      tr.classList.add("opacity-50");
    }
    tr.innerHTML = `
      <td class="p-2">
        <div class="${!c.connected ? 'text-red-400' : ''}">
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

async function connectWS() {
  socket = new WebSocket(((location.protocol === 'https:') ? 'wss://' : 'ws://') + window.location.host + '/ws/clients');
  socket.onopen = () => console.log('WS open');
  socket.onclose = () => setTimeout(connectWS, 3000);
  socket.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    document.getElementById('totalClients').textContent = data.total;
    document.getElementById('connectedClients').textContent = data.connected;
    populateClients(data.list || data.clients || []);
  };
}

async function refreshClients() {
  try {
    const res = await fetch('/api/clients');
    const data = await res.json();
    document.getElementById("totalClients").textContent = data.total;
    // Determine connected count
    const arr = data.clients || [];
    const active = arr.filter(c => c.connected);
    document.getElementById("connectedClients").textContent = active.length;
    populateClients(arr);
  } catch (err) {
    console.error("Failed to update clients:", err);
  }
}

// Modal & actions (QR, config, download, delete) unchanged
async function showQR(name) { /* ... */ }
function hideQR() { /* ... */ }
async function showConfig(name) { /* ... */ }
function hideConfig() { /* ... */ }
function downloadConfig(name) { /* ... */ }
async function deleteConfig(name) { /* ... */ }

// Startup
window.addEventListener('load', () => {
  refreshClients();
  connectWS();
  document.getElementById('clientSelect').addEventListener('change', (e) => {
    if (e.target.value) loadHistory(e.target.value);
  });
});
