const ORCHESTRATOR_URL = "http://localhost:8080";

// Intervalli
let pollInterval;
const POLL_RATE = 3000;

document.addEventListener("DOMContentLoaded", () => {
    fetchContainers();
    pollInterval = setInterval(fetchContainers, POLL_RATE);
});

// APIs
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = { method, headers: { 'Content-Type': 'application/json' }};
        if (body) options.body = JSON.stringify(body);
        const res = await fetch(`${ORCHESTRATOR_URL}${endpoint}`, options);
        if(!res.ok) throw new Error(await res.text());
        return await res.json();
    } catch(err) {
        console.error(`API Error (${endpoint}):`, err);
        throw err;
    }
}

async function fetchContainers() {
    try {
        const containers = await apiCall('/containers');
        const grid = document.getElementById('containers-grid');
        
        if (containers.length === 0) {
            grid.innerHTML = `
                <div class="col-span-3 text-center py-16 glass-panel">
                    <div class="text-blue-500 mb-4 opacity-50"><i class="fa-solid fa-box-open text-6xl"></i></div>
                    <h3 class="text-xl font-semibold mb-2">Nessun servizio in esecuzione</h3>
                    <p class="text-slate-400">Clicca su "Nuovo Servizio" in alto a destra per crearne uno dal template.</p>
                </div>`;
            return;
        }

        // Render Cards
        grid.innerHTML = '';
        let activeCount = 0;
        
        for (const c of containers) {
            if(c.status === 'running') activeCount++;
            
            // Per il mock di statistiche immediate prima del fetch reale
            const isRunning = c.status === 'running';
            const statusClass = isRunning ? 'status-running' : 'status-stopped';
            const statusText = isRunning ? 'Online' : 'Stopped';
            
            // UI Card
            const card = document.createElement('div');
            card.className = 'glass-panel p-6 relative overflow-hidden flex flex-col justify-between';
            card.innerHTML = `
                <div class="absolute top-0 right-0 p-4 opacity-10">
                    <i class="fa-brands fa-docker text-6xl text-blue-400"></i>
                </div>
                
                <div class="relative z-10">
                    <div class="flex justify-between items-start mb-4">
                        <div class="flex items-center gap-2">
                            <span class="status-dot ${statusClass}"></span>
                            <span class="text-xs uppercase tracking-wider font-semibold text-slate-400">${statusText}</span>
                        </div>
                        <span class="text-xs font-mono text-slate-500 bg-slate-800/50 px-2 py-1 rounded">ID: ${c.id}</span>
                    </div>
                    
                    <h3 class="text-xl font-bold mb-1 truncate text-white" title="${c.name}">${c.name.replace('srv_','').replace('_',' ')}</h3>
                    <p class="text-sm text-slate-400 mb-6 truncate"><i class="fa-solid fa-layer-group text-purple-400 mr-1"></i> ${c.image}</p>
                    
                    <div class="space-y-4" id="stats-${c.id}">
                        ${isRunning ? `
                        <div>
                            <div class="flex justify-between text-xs mb-1">
                                <span class="text-slate-400"><i class="fa-solid fa-microchip mr-1"></i> CPU</span>
                                <span class="font-mono text-blue-400 stat-val">...</span>
                            </div>
                            <div class="w-full h-1.5 progress-bar-bg rounded-full overflow-hidden">
                                <div class="h-full progress-bar-fill w-0 stat-bar"></div>
                            </div>
                        </div>
                        <div>
                            <div class="flex justify-between text-xs mb-1">
                                <span class="text-slate-400"><i class="fa-solid fa-memory mr-1"></i> RAM</span>
                                <span class="font-mono text-purple-400 stat-val">...</span>
                            </div>
                            <div class="w-full h-1.5 progress-bar-bg rounded-full overflow-hidden">
                                <div class="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500 w-0 stat-bar"></div>
                            </div>
                        </div>
                        ` : `<div class="py-4 text-center text-sm text-slate-500 border border-slate-700/50 rounded-lg bg-slate-800/30">Container Offline</div>`}
                    </div>
                </div>
                
                <div class="mt-6 pt-4 border-t border-slate-700/50 flex justify-between relative z-10">
                    <div class="flex gap-2">
                         ${isRunning ? 
                            `<button onclick="actionContainer('${c.id}', 'stop')" class="h-9 px-4 rounded-lg bg-slate-800 hover:bg-red-500/20 text-slate-300 hover:text-red-400 border border-slate-700 hover:border-red-500/50 transition-all text-sm font-medium"><i class="fa-solid fa-stop mr-1"></i> Stop</button>` : 
                            `<button onclick="actionContainer('${c.id}', 'start')" class="h-9 px-4 rounded-lg bg-slate-800 hover:bg-emerald-500/20 text-slate-300 hover:text-emerald-400 border border-slate-700 hover:border-emerald-500/50 transition-all text-sm font-medium"><i class="fa-solid fa-play mr-1"></i> Start</button>`
                          }
                    </div>
                    <button class="h-9 w-9 rounded-lg bg-slate-800 hover:bg-blue-500/20 text-slate-400 hover:text-blue-400 border border-slate-700 hover:border-blue-500/50 transition-all flex items-center justify-center">
                        <i class="fa-solid fa-terminal text-xs"></i>
                    </button>
                </div>
            `;
            grid.appendChild(card);
            
            // Trigger stats loading se in esecuzione
            if(isRunning) loadStats(c.id);
        }
        
        document.getElementById('stat-active').innerText = activeCount;
        
    } catch (e) {
        document.getElementById('containers-grid').innerHTML = `
            <div class="col-span-3 text-center py-10 text-red-400">
                <i class="fa-solid fa-triangle-exclamation text-4xl mb-3"></i>
                <p>Impossibile connettersi all'Orchestratore Backend sulla porta 8080.</p>
                <p class="text-sm mt-2 opacity-70">Verifica che l'API FastAPI sia in esecuzione (uvicorn main:app --port 8080)</p>
            </div>`;
    }
}

async function loadStats(id) {
    try {
        const stats = await apiCall(`/containers/${id}/stats`);
        const statsContainer = document.getElementById(`stats-${id}`);
        if(statsContainer && stats.status === "running") {
            const vals = statsContainer.querySelectorAll('.stat-val');
            const bars = statsContainer.querySelectorAll('.stat-bar');
            
            if(vals.length >= 2) {
                vals[0].innerText = `${stats.cpu_percent}%`;
                bars[0].style.width = `${Math.min(stats.cpu_percent, 100)}%`;
                
                vals[1].innerText = `${stats.mem_percent}% (${stats.mem_usage_mb}MB)`;
                bars[1].style.width = `${Math.min(stats.mem_percent, 100)}%`;
                
                // Opzionale: update total dashboard stats (molto semplificato)
                // Questo richiederebbe stato globale reale
            }
        }
    } catch(e) { }
}

async function actionContainer(id, action) {
    try {
        await apiCall(`/containers/${id}/${action}`, 'POST');
        fetchContainers(); // Aggiorna subito
    } catch(e) {
        alert("Errore durante " + action + ": " + e.message);
    }
}

async function createService(e) {
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Generazione...';
    btn.disabled = true;
    
    const body = {
        service_name: document.getElementById('svc-name').value,
        template_name: document.getElementById('svc-template').value,
        cpu_cores: parseFloat(document.getElementById('svc-cpu').value),
        mem_limit_mb: parseInt(document.getElementById('svc-mem').value)
    };
    
    try {
        await apiCall('/services/create', 'POST', body);
        closeModal();
        setTimeout(fetchContainers, 1500); // refresh delayed for container to appear
    } catch(e) {
        alert("Errore generazione: " + e.message);
    } finally {
        btn.innerHTML = '<i class="fa-solid fa-rocket"></i> Avvia Generazione';
        btn.disabled = false;
    }
}

// Modal handling
function openModal() {
    const m = document.getElementById('createModal');
    const c = document.getElementById('modalContent');
    m.classList.remove('hidden');
    m.classList.add('flex');
    setTimeout(() => { c.classList.remove('scale-95', 'opacity-0'); }, 10);
}

function closeModal() {
    const m = document.getElementById('createModal');
    const c = document.getElementById('modalContent');
    c.classList.add('scale-95', 'opacity-0');
    setTimeout(() => { 
        m.classList.add('hidden');
        m.classList.remove('flex');
    }, 300);
}
