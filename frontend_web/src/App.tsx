import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play, Square, Plus, Server, Activity,
  Cpu, MemoryStick, AlertCircle, CheckCircle2,
  Info, X, Trash2, ExternalLink
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- CONFIG ---
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

// --- TYPES ---
interface Container {
  id: string;
  name: string;
  status: string;
  image: string;
  ports: any;
}

interface ContainerStats {
  status: string;
  cpu_percent: number;
  mem_usage_mb: number;
  mem_limit_mb: number;
  mem_percent: number;
  started_at: string;
}

interface ToastMessage {
  id: string;
  title: string;
  description: string;
  type: 'success' | 'error' | 'info';
}

// --- COMPONENTS ---
const Toast = ({ toast, onClose }: { toast: ToastMessage; onClose: (id: string) => void }) => {
  useEffect(() => {
    const timer = setTimeout(() => onClose(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onClose]);

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    error: <AlertCircle className="w-5 h-5 text-rose-400" />,
    info: <Info className="w-5 h-5 text-sky-400" />
  };

  const bgs = {
    success: 'bg-emerald-500/10 border-emerald-500/20',
    error: 'bg-rose-500/10 border-rose-500/20',
    info: 'bg-sky-500/10 border-sky-500/20'
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
      className={cn("flex gap-3 p-4 rounded-xl border backdrop-blur-md shadow-lg w-80", bgs[toast.type])}
    >
      <div className="flex-shrink-0 mt-0.5">{icons[toast.type]}</div>
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-white">{toast.title}</h4>
        <p className="text-xs text-slate-300 mt-1 leading-relaxed">{toast.description}</p>
      </div>
      <button onClick={() => onClose(toast.id)} className="flex-shrink-0 text-slate-400 hover:text-white transition-colors">
        <X className="w-4 h-4" />
      </button>
    </motion.div>
  );
};

export default function App() {
  const [containers, setContainers] = useState<Container[]>([]);
  const [stats, setStats] = useState<Record<string, ContainerStats>>({});
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Modal Form State
  const [formParams, setFormParams] = useState({
    service_name: '',
    template_name: 'template_service',
    cpu_cores: 1.0,
    mem_limit_mb: 512
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const addToast = useCallback((title: string, description: string, type: ToastMessage['type'] = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { id, title, description, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const fetchContainers = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/containers`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setContainers(data);
      setIsLoading(false);
    } catch (err) {
      console.error(err);
      if (!isLoading) addToast("Errore Connessione", "Impossibile recuperare la lista dei container.", "error");
    }
  }, [addToast, isLoading]);

  const fetchStats = useCallback(async () => {
    // Fetch stats only for running containers
    const running = containers.filter(c => c.status === 'running');
    for (const c of running) {
      try {
        const res = await fetch(`${API_URL}/containers/${c.id}/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats(prev => ({ ...prev, [c.id]: data }));
        }
      } catch (e) {
        // ignore individual stat fetch err to not spam toasts
      }
    }
  }, [containers]);

  // Main Polling Effect
  useEffect(() => {
    fetchContainers();
    const interval = setInterval(() => {
      fetchContainers();
      fetchStats();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchContainers, fetchStats]);

  const handleAction = async (id: string, action: 'start' | 'stop' | 'delete') => {
    try {
      // Optimistic update
      if (action !== 'delete') {
        setContainers(prev => prev.map(c =>
          c.id === id ? { ...c, status: action === 'start' ? 'starting' : 'stopping' } : c
        ));
      } else {
        setContainers(prev => prev.map(c =>
          c.id === id ? { ...c, status: 'deleting' } : c
        ));
      }

      const method = action === 'delete' ? 'DELETE' : 'POST';
      const url = action === 'delete' ? `${API_URL}/containers/${id}` : `${API_URL}/containers/${id}/${action}`;

      const res = await fetch(url, { method });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || `Azione fallita: ${res.status}`);
      }

      addToast(
        action === 'start' ? "Container Avviato" : action === 'stop' ? "Container Arrestato" : "Container Eliminato",
        `Comando inviato con successo al container.`,
        "success"
      );
      fetchContainers();
    } catch (err: any) {
      addToast("Errore di Esecuzione", err.message, "error");
      fetchContainers(); // Revert optimistic update
    }
  };

  const getExternalPort = (ports: any) => {
    if (!ports) return null;
    for (const key in ports) {
      if (ports[key] && ports[key].length > 0) {
        return ports[key][0].HostPort;
      }
    }
    return null;
  };

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formParams.service_name.trim()) {
      addToast("Errore Validazione", "Il nome del servizio è obbligatorio", "error");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/services/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formParams)
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Creazione fallita");

      addToast("Deploy Iniziato", `Servizio '${formParams.service_name}' in costruzione asincrona.`, "success");
      setIsModalOpen(false);
      setFormParams(prev => ({ ...prev, service_name: '' }));
      setTimeout(fetchContainers, 2000); // Trigger a fetch soon
    } catch (err: any) {
      addToast("Deploy Fallito", err.message, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#020817] text-slate-50 relative overflow-hidden font-sans">
      {/* Background Glows */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-500/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/10 blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="border-b border-slate-800/60 bg-slate-950/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                Symphony Orchestrator
              </h1>
              <p className="text-xs text-slate-500 font-medium tracking-wide uppercase">Computer Vision Platform</p>
            </div>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-[0_0_20px_rgba(79,70,229,0.3)] hover:shadow-[0_0_25px_rgba(79,70,229,0.5)] active:scale-95"
          >
            <Plus className="w-4 h-4" /> Nuovo Servizio
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-10 relative z-10">

        {/* System Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {[
            { label: "Container Attivi", value: containers.filter(c => c.status === 'running').length, icon: Server, color: "text-emerald-400" },
            { label: "Consumo CPU Medio", value: `${(Object.values(stats).reduce((acc, s) => acc + s.cpu_percent, 0) / (Object.values(stats).length || 1)).toFixed(1)}%`, icon: Cpu, color: "text-blue-400" },
            { label: "Consumo RAM Totale", value: `${Object.values(stats).reduce((acc, s) => acc + s.mem_usage_mb, 0).toFixed(0)} MB`, icon: MemoryStick, color: "text-indigo-400" }
          ].map((stat, i) => (
            <motion.div
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
              key={i} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm"
            >
              <div className="flex items-center gap-4">
                <div className={cn("p-3 rounded-xl bg-slate-800/80", stat.color)}>
                  <stat.icon className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-400">{stat.label}</p>
                  <p className="text-2xl font-bold text-white mt-1">{stat.value}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Containers Grid */}
        <h2 className="text-lg font-semibold text-slate-200 mb-6 flex items-center gap-2">
          <Server className="w-5 h-5 text-slate-400" /> Servizi Deployed
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
          </div>
        ) : containers.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-slate-800 rounded-2xl bg-slate-900/20">
            <Server className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300">Nessun Container Trovato</h3>
            <p className="text-slate-500 mt-2">Crea un nuovo servizio dal bottone in alto a destra.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AnimatePresence>
              {containers.map((container) => {
                const isRunning = container.status === 'running';
                const isDeleting = container.status === 'deleting';
                const cStats = stats[container.id];
                const activePort = getExternalPort(container.ports);

                if (isDeleting) return null;

                return (
                  <motion.div
                    layout
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    key={container.id}
                    className="group bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 transition-all backdrop-blur-sm relative"
                  >
                    <div className="absolute top-6 right-6 flex gap-2">
                      {isRunning ? (
                        <>
                          {activePort && (
                            <a href={`http://localhost:${activePort}/docs`} target="_blank" rel="noreferrer" className="p-2 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-colors flex items-center gap-1.5 px-3 font-medium text-sm" title="Apri Swagger UI CV">
                              <ExternalLink className="w-4 h-4" /> API Docs
                            </a>
                          )}
                          <button onClick={() => handleAction(container.id, 'stop')} className="p-2 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg transition-colors" title="Ferma Container">
                            <Square className="w-4 h-4 fill-current" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => handleAction(container.id, 'start')} className="p-2 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors" title="Avvia Container">
                            <Play className="w-4 h-4 fill-current" />
                          </button>
                          <button onClick={() => handleAction(container.id, 'delete')} className="p-2 bg-slate-800 text-slate-400 hover:bg-rose-500/20 hover:text-rose-400 rounded-lg transition-colors" title="Elimina Container">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>

                    <div className="flex justify-between items-start mb-6">
                      <div className="pr-20">
                        <div className="flex items-center gap-3 mb-2">
                          <div className={cn("w-2.5 h-2.5 rounded-full shadow-[0_0_10px_currentColor]", isRunning ? "text-emerald-500 bg-emerald-500" : "text-slate-500 bg-slate-500")} />
                          <h3 className="text-xl font-semibold text-white truncate max-w-[200px]" title={container.name}>{container.name}</h3>
                        </div>
                        <p className="text-xs text-slate-500 font-mono truncate max-w-[200px]">{container.image}</p>
                      </div>
                    </div>

                    {/* Stats Section */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/50">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5" /> CPU Usage</span>
                          <span className="text-sm font-semibold text-slate-200">{isRunning && cStats ? `${cStats.cpu_percent}%` : '0%'}</span>
                        </div>
                        <div className="w-full bg-slate-800/50 rounded-full h-1.5">
                          <motion.div
                            className="bg-blue-500 h-1.5 rounded-full"
                            initial={{ width: 0 }}
                            animate={{ width: `${isRunning && cStats ? Math.min(cStats.cpu_percent, 100) : 0}%` }}
                            transition={{ ease: "linear", duration: 1 }}
                          />
                        </div>
                      </div>

                      <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/50">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5"><MemoryStick className="w-3.5 h-3.5" /> RAM Usage</span>
                          <span className="text-sm font-semibold text-slate-200">{isRunning && cStats ? `${cStats.mem_usage_mb}MB` : '0MB'}</span>
                        </div>
                        <div className="w-full bg-slate-800/50 rounded-full h-1.5">
                          <motion.div
                            className="bg-indigo-500 h-1.5 rounded-full"
                            initial={{ width: 0 }}
                            animate={{ width: `${isRunning && cStats ? cStats.mem_percent : 0}%` }}
                            transition={{ ease: "linear", duration: 1 }}
                          />
                        </div>
                      </div>
                    </div>

                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Create Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md relative z-10 shadow-2xl overflow-hidden"
            >
              <div className="p-6 border-b border-slate-800 flex justify-between items-center">
                <h3 className="text-lg font-bold text-white flex items-center gap-2"><Plus className="w-5 h-5 text-indigo-400" /> Nuovo Servizio CV</h3>
                <button type="button" onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
              </div>

              <form onSubmit={handleCreateService} className="p-6 space-y-5">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1.5">Nome Servizio (senza spazi)</label>
                  <input required type="text"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-mono"
                    placeholder="rifiuti-classifier-2"
                    value={formParams.service_name}
                    onChange={e => setFormParams({ ...formParams, service_name: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">CPU Cores</label>
                    <input type="number" step="0.5" min="0.5"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                      value={formParams.cpu_cores}
                      onChange={e => setFormParams({ ...formParams, cpu_cores: parseFloat(e.target.value) })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">RAM Limit (MB)</label>
                    <input type="number" step="128" min="128"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                      value={formParams.mem_limit_mb}
                      onChange={e => setFormParams({ ...formParams, mem_limit_mb: parseInt(e.target.value) })}
                    />
                  </div>
                </div>

                <div className="pt-4 flex gap-3">
                  <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 px-4 py-3 border border-slate-700 text-slate-300 rounded-xl font-medium hover:bg-slate-800 transition-colors">
                    Annulla
                  </button>
                  <button type="submit" disabled={isSubmitting} className="flex-1 px-4 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors shadow-lg shadow-indigo-500/20 flex justify-center items-center">
                    {isSubmitting ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : "Distribuisci (Deploy)"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Toasts Container */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
        <AnimatePresence>
          {toasts.map(toast => (
            <Toast key={toast.id} toast={toast} onClose={removeToast} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
