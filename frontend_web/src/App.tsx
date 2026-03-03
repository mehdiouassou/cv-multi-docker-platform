import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play, Square, Plus, Server, Activity,
  Cpu, MemoryStick, AlertCircle, CheckCircle2,
  Info, X, Trash2, ExternalLink, TerminalSquare,
  RefreshCw, Upload, Clock, Globe, ImageIcon, RotateCcw,
  FileCode2, Rocket, Loader2
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// --- CONFIG ---
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const POLL_INTERVAL = 3000;

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
  mem_limit_mb: number | null;  // null = nessun limite esplicito impostato
  has_mem_limit: boolean;
  mem_percent: number;
  started_at: string;
}

interface ServiceInfo {
  name: string;
  capabilities: {
    algorithm: string;
    classes?: string[];
    [key: string]: any;
  };
}

interface InferenceResult {
  result: string;
  confidence: number;
  latency_ms: number;
}

interface ToastMessage {
  id: string;
  title: string;
  description: string;
  type: 'success' | 'error' | 'info';
}

interface PendingService {
  service_name: string;
  status: 'pending_setup' | 'building' | 'build_failed';
  created_at: string;
  error?: string;
  files_to_edit: string[];
}

// Calcola uptime leggibile da una data ISO
function formatUptime(startedAt: string): string {
  try {
    const diff = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s`;
    const hours = Math.floor(diff / 3600);
    const mins = Math.floor((diff % 3600) / 60);
    if (hours < 24) return `${hours}h ${mins}m`;
    return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  } catch {
    return '--';
  }
}

// Componente che aggiorna l'uptime ogni secondo in autonomia,
// senza dipendere dal polling dei container (che avviene ogni 3s).
const LiveUptime = ({ startedAt }: { startedAt: string }) => {
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return <>{formatUptime(startedAt)}</>;
};

// Componente per numeri che si aggiornano con transizione fluida.
// Usa tabular-nums per evitare che le cifre "saltino" quando cambiano larghezza.
const SmoothNumber = ({ value, suffix = '' }: { value: string; suffix?: string }) => (
  <span className="tabular-nums transition-all duration-700 ease-out inline-block min-w-[3ch] text-right">
    {value}{suffix}
  </span>
);

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
  const [healthMap, setHealthMap] = useState<Record<string, boolean>>({});
  const [serviceInfoMap, setServiceInfoMap] = useState<Record<string, ServiceInfo | null>>({});
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingServices, setPendingServices] = useState<PendingService[]>([]);

  const [inFlightActions, setInFlightActions] = useState<Set<string>>(new Set());

  // Inference state per container
  const [inferenceStates, setInferenceStates] = useState<Record<string, {
    isLoading: boolean;
    result: InferenceResult | null;
    error: string | null;
    previewUrl: string | null;
  }>>({});

  // Logs Modal
  const [logsModalState, setLogsModalState] = useState({
    isOpen: false, containerId: '', containerName: '', logs: '', isLoading: false
  });

  // Create Modal Form
  const [formParams, setFormParams] = useState({
    service_name: '', template_name: 'template_service', cpu_cores: 1.0, mem_limit_mb: 512
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Refs per stabilizzare il polling
  const containersRef = useRef<Container[]>([]);
  const inFlightRef = useRef<Set<string>>(new Set());
  const hasLoadedOnce = useRef(false);

  useEffect(() => { containersRef.current = containers; }, [containers]);
  useEffect(() => { inFlightRef.current = inFlightActions; }, [inFlightActions]);

  const addToast = useCallback((title: string, description: string, type: ToastMessage['type'] = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { id, title, description, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const getExternalPort = (ports: any): string | null => {
    if (!ports) return null;
    for (const key in ports) {
      if (ports[key] && ports[key].length > 0) return ports[key][0].HostPort;
    }
    return null;
  };

  // Fetch lista container
  const fetchContainers = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/containers`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Container[] = await res.json();

      const prev = containersRef.current;
      const changed = data.length !== prev.length ||
        data.some((c, i) => !prev[i] || c.id !== prev[i].id || c.status !== prev[i].status);

      if (changed) {
        const flying = inFlightRef.current;
        setContainers(current =>
          data.map(c => {
            if (flying.has(c.id)) {
              const existing = current.find(e => e.id === c.id);
              if (existing) return existing;
            }
            return c;
          })
        );
      }

      if (!hasLoadedOnce.current) {
        hasLoadedOnce.current = true;
        setIsLoading(false);
      }
    } catch (err) {
      console.error('Errore fetch containers:', err);
      if (hasLoadedOnce.current) {
        addToast("Errore Connessione", "Impossibile recuperare la lista dei container.", "error");
      }
    }
  }, [addToast]);

  // Fetch stats + health + info per container running (tutto via proxy backend, no CORS)
  const fetchStats = useCallback(async () => {
    const running = containersRef.current.filter(c => c.status === 'running');
    if (running.length === 0) {
      setStats({});
      setHealthMap({});
      return;
    }

    const results = await Promise.allSettled(
      running.map(async (c) => {
        // Stats, health e info in parallelo per ogni container
        const [statsRes, healthRes, infoRes] = await Promise.allSettled([
          fetch(`${API_URL}/containers/${c.id}/stats`).then(r => r.ok ? r.json() : null),
          fetch(`${API_URL}/containers/${c.id}/health`).then(r => r.ok ? r.json() : null),
          fetch(`${API_URL}/containers/${c.id}/info`).then(r => r.ok ? r.json() : null),
        ]);

        return {
          id: c.id,
          stats: statsRes.status === 'fulfilled' ? statsRes.value : null,
          health: healthRes.status === 'fulfilled' ? healthRes.value : null,
          info: infoRes.status === 'fulfilled' ? infoRes.value : null,
        };
      })
    );

    const newStats: Record<string, ContainerStats> = {};
    const newHealth: Record<string, boolean> = {};
    const newInfo: Record<string, ServiceInfo | null> = {};

    for (const result of results) {
      if (result.status === 'fulfilled' && result.value) {
        const { id, stats: s, health: h, info: inf } = result.value;
        if (s) newStats[id] = s;
        newHealth[id] = h?.status === 'ok';
        if (inf && !inf.error) newInfo[id] = inf;
      }
    }

    setStats(newStats);
    setHealthMap(newHealth);
    setServiceInfoMap(prev => ({ ...prev, ...newInfo }));
  }, []);

  // Fetch servizi in attesa di setup / build
  const fetchPendingServices = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/services/pending`);
      if (!res.ok) return;
      const data: PendingService[] = await res.json();
      setPendingServices(data);
    } catch {
      // silenzioso: il polling riprova
    }
  }, []);

  // Polling stabile
  useEffect(() => {
    fetchContainers();
    fetchStats();
    fetchPendingServices();
    const interval = setInterval(() => {
      fetchContainers();
      fetchStats();
      fetchPendingServices();
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchContainers, fetchStats, fetchPendingServices]);

  const handleAction = async (id: string, action: 'start' | 'stop' | 'restart' | 'delete') => {
    try {
      setInFlightActions(prev => new Set(prev).add(id));

      if (action === 'delete') {
        setContainers(prev => prev.map(c => c.id === id ? { ...c, status: 'removing...' } : c));
      } else {
        const statusMap: Record<string, string> = { start: 'starting...', stop: 'stopping...', restart: 'restarting...' };
        setContainers(prev => prev.map(c =>
          c.id === id ? { ...c, status: statusMap[action] ?? action } : c
        ));
      }

      const method = action === 'delete' ? 'DELETE' : 'POST';
      const url = action === 'delete' ? `${API_URL}/containers/${id}` : `${API_URL}/containers/${id}/${action}`;
      const res = await fetch(url, { method });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Azione fallita: ${res.status}`);

      const labels: Record<string, string> = { start: "Container Avviato", stop: "Container Arrestato", restart: "Container Riavviato", delete: "Container Eliminato" };
      addToast(labels[action], "Comando eseguito con successo.", "success");

      setInFlightActions(prev => { const n = new Set(prev); n.delete(id); return n; });
      await new Promise(r => setTimeout(r, 500));
      await fetchContainers();
      await fetchStats();
    } catch (err: any) {
      addToast("Errore", err.message, "error");
      setInFlightActions(prev => { const n = new Set(prev); n.delete(id); return n; });
      await fetchContainers();
    }
  };

  // Inferenza via proxy backend (evita CORS)
  const handleInference = async (containerId: string, file: File) => {
    const previewUrl = URL.createObjectURL(file);
    setInferenceStates(prev => ({
      ...prev,
      [containerId]: { isLoading: true, result: null, error: null, previewUrl }
    }));

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/containers/${containerId}/inference`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `Errore inferenza`);
      }

      const data: InferenceResult = await res.json();
      setInferenceStates(prev => ({
        ...prev,
        [containerId]: { isLoading: false, result: data, error: null, previewUrl }
      }));
    } catch (err: any) {
      setInferenceStates(prev => ({
        ...prev,
        [containerId]: { isLoading: false, result: null, error: err.message, previewUrl }
      }));
    }
  };

  const openLogs = async (id: string, name: string) => {
    setLogsModalState({ isOpen: true, containerId: id, containerName: name, logs: '', isLoading: true });
    try {
      const res = await fetch(`${API_URL}/containers/${id}/logs`);
      if (!res.ok) throw new Error("Errore nel caricamento dei log");
      const data = await res.json();
      setLogsModalState(prev => ({ ...prev, logs: data.logs, isLoading: false }));
    } catch (err: any) {
      setLogsModalState(prev => ({ ...prev, logs: err.message, isLoading: false }));
    }
  };

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formParams.service_name.trim()) {
      addToast("Errore Validazione", "Il nome del servizio e' obbligatorio.", "error");
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

      addToast("Template Creato", `Modifica i file di '${formParams.service_name}' e poi clicca Build & Deploy.`, "success");
      setIsModalOpen(false);
      setFormParams(prev => ({ ...prev, service_name: '' }));
      await fetchPendingServices();
    } catch (err: any) {
      addToast("Creazione Fallita", err.message, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBuildService = async (serviceName: string) => {
    try {
      const res = await fetch(`${API_URL}/services/${serviceName}/build`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Build fallito");
      addToast("Build Avviato", `Build di '${serviceName}' in corso...`, "info");
      await fetchPendingServices();
    } catch (err: any) {
      addToast("Errore Build", err.message, "error");
    }
  };

  const handleDeletePendingService = async (serviceName: string) => {
    try {
      const res = await fetch(`${API_URL}/services/${serviceName}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Eliminazione fallita");
      addToast("Servizio Eliminato", `'${serviceName}' rimosso.`, "success");
      await fetchPendingServices();
    } catch (err: any) {
      addToast("Errore", err.message, "error");
    }
  };

  const handleManualRefresh = async () => {
    await fetchContainers();
    await fetchStats();
    addToast("Aggiornato", "Lista container e statistiche aggiornate.", "info");
  };

  // Statistiche aggregate
  const statsValues = Object.values(stats);
  const runningCount = containers.filter(c => c.status === 'running').length;
  const avgCpu = statsValues.length > 0
    ? (statsValues.reduce((acc, s) => acc + s.cpu_percent, 0) / statsValues.length).toFixed(1)
    : '0.0';
  const totalRam = statsValues.length > 0
    ? statsValues.reduce((acc, s) => acc + s.mem_usage_mb, 0).toFixed(0)
    : '0';

  return (
    <div className="min-h-screen bg-[#020817] text-slate-50 relative overflow-hidden font-sans">
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
          <div className="flex items-center gap-3">
            <button onClick={handleManualRefresh}
              className="p-2.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              title="Aggiorna manualmente">
              <RefreshCw className="w-4 h-4" />
            </button>
            <button onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg font-medium transition-all shadow-[0_0_20px_rgba(79,70,229,0.3)] hover:shadow-[0_0_25px_rgba(79,70,229,0.5)] active:scale-95">
              <Plus className="w-4 h-4" /> Nuovo Servizio
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10 relative z-10">

        {/* Summary cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {[
            { label: "Container Attivi", value: runningCount, icon: Server, color: "text-emerald-400" },
            { label: "CPU Media", value: `${avgCpu}%`, icon: Cpu, color: "text-blue-400" },
            { label: "RAM Totale", value: `${totalRam} MB`, icon: MemoryStick, color: "text-indigo-400" }
          ].map((stat) => (
            <div key={stat.label} className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm">
              <div className="flex items-center gap-4">
                <div className={cn("p-3 rounded-xl bg-slate-800/80", stat.color)}>
                  <stat.icon className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-400">{stat.label}</p>
                  <p className="text-2xl font-bold text-white mt-1">{stat.value}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Pending Services */}
        {pendingServices.length > 0 && (
          <div className="mb-10">
            <h2 className="text-lg font-semibold text-slate-200 mb-6 flex items-center gap-2">
              <FileCode2 className="w-5 h-5 text-amber-400" /> Servizi in Attesa di Setup
            </h2>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              {pendingServices.map((svc) => {
                const isBuilding = svc.status === 'building';
                const isFailed = svc.status === 'build_failed';
                return (
                  <div key={svc.service_name}
                    className={cn(
                      "bg-slate-900/60 border rounded-2xl p-6 backdrop-blur-sm",
                      isFailed ? "border-rose-500/40" : "border-amber-500/40"
                    )}>
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-2.5 h-2.5 rounded-full",
                          isBuilding ? "bg-amber-500 animate-pulse shadow-[0_0_8px_theme(colors.amber.500)]" :
                          isFailed ? "bg-rose-500 shadow-[0_0_8px_theme(colors.rose.500)]" :
                          "bg-indigo-500 shadow-[0_0_8px_theme(colors.indigo.500)]"
                        )} />
                        <h3 className="text-lg font-semibold text-white">{svc.service_name}</h3>
                        <span className={cn(
                          "text-xs px-2 py-0.5 rounded-full font-medium",
                          isBuilding ? "bg-amber-500/10 text-amber-400" :
                          isFailed ? "bg-rose-500/10 text-rose-400" :
                          "bg-indigo-500/10 text-indigo-400"
                        )}>
                          {isBuilding ? 'building...' : isFailed ? 'build fallito' : 'da configurare'}
                        </span>
                      </div>
                      <button onClick={() => handleDeletePendingService(svc.service_name)}
                        className="p-2 bg-slate-800 text-slate-400 hover:bg-rose-500/20 hover:text-rose-400 rounded-lg transition-colors" title="Elimina">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Files da modificare */}
                    {svc.status === 'pending_setup' && (
                      <div className="mb-4 p-4 bg-slate-950/50 rounded-xl border border-slate-800/50">
                        <p className="text-sm text-slate-300 mb-2">Modifica questi file prima di buildare:</p>
                        <ul className="space-y-1">
                          {svc.files_to_edit.map((f) => (
                            <li key={f} className="text-xs font-mono text-indigo-400 flex items-center gap-2">
                              <FileCode2 className="w-3.5 h-3.5 flex-shrink-0" />
                              {f}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Errore build */}
                    {isFailed && svc.error && (
                      <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                        <p className="text-xs text-rose-400 font-mono break-all">{svc.error}</p>
                      </div>
                    )}

                    {/* Build button */}
                    <button
                      onClick={() => handleBuildService(svc.service_name)}
                      disabled={isBuilding}
                      className={cn(
                        "w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-medium transition-all",
                        isBuilding
                          ? "bg-amber-500/20 text-amber-400 cursor-not-allowed"
                          : isFailed
                            ? "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-500/20"
                            : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
                      )}>
                      {isBuilding ? (
                        <><Loader2 className="w-4 h-4 animate-spin" /> Build in corso...</>
                      ) : isFailed ? (
                        <><RotateCcw className="w-4 h-4" /> Riprova Build</>
                      ) : (
                        <><Rocket className="w-4 h-4" /> Build &amp; Deploy</>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Containers */}
        <h2 className="text-lg font-semibold text-slate-200 mb-6 flex items-center gap-2">
          <Server className="w-5 h-5 text-slate-400" /> Servizi Deployed
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
          </div>
        ) : containers.length === 0 ? (
          <div className="text-center py-20 border border-dashed border-slate-800 rounded-2xl bg-slate-900/20">
            <Server className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-300">Nessun Container Trovato</h3>
            <p className="text-slate-500 mt-2">Crea un nuovo servizio dal bottone in alto a destra.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {containers.map((container) => {
              const isRunning = container.status === 'running';
              const isTransitioning = container.status.endsWith('...');
              const cStats = stats[container.id];
              const isHealthy = healthMap[container.id] ?? false;
              const svcInfo = serviceInfoMap[container.id];
              const activePort = getExternalPort(container.ports);
              const actionDisabled = inFlightActions.has(container.id) || isTransitioning;
              const infState = inferenceStates[container.id];

              // Mostra la sezione inferenza solo se il servizio ha classes nelle capabilities
              // (cioe e' un servizio CV con classificazione, non un template generico)
              const supportsInference = svcInfo?.capabilities?.classes && svcInfo.capabilities.classes.length > 0;

              return (
                <div key={container.id}
                  className="group bg-slate-900/60 border border-slate-800 hover:border-slate-700 rounded-2xl p-6 transition-colors backdrop-blur-sm relative">

                  {/* Action buttons */}
                  <div className="absolute top-6 right-6 flex gap-2">
                    {isRunning ? (
                      <>
                        {activePort && (
                          <a href={`http://localhost:${activePort}/docs`} target="_blank" rel="noreferrer"
                            className="p-2 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded-lg transition-colors flex items-center gap-1.5 px-3 font-medium text-sm"
                            title="Apri Swagger UI">
                            <ExternalLink className="w-4 h-4" /> API
                          </a>
                        )}
                        <button disabled={actionDisabled} onClick={() => openLogs(container.id, container.name)}
                          className="p-2 bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white rounded-lg transition-colors" title="Vedi Log">
                          <TerminalSquare className="w-4 h-4" />
                        </button>
                        <button disabled={actionDisabled} onClick={() => handleAction(container.id, 'restart')}
                          className="p-2 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors" title="Riavvia">
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        <button disabled={actionDisabled} onClick={() => handleAction(container.id, 'stop')}
                          className="p-2 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors" title="Ferma">
                          <Square className="w-4 h-4 fill-current" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button disabled={actionDisabled} onClick={() => openLogs(container.id, container.name)}
                          className="p-2 bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white rounded-lg transition-colors" title="Vedi Log">
                          <TerminalSquare className="w-4 h-4" />
                        </button>
                        <button disabled={actionDisabled} onClick={() => handleAction(container.id, 'start')}
                          className="p-2 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors" title="Avvia">
                          <Play className="w-4 h-4 fill-current" />
                        </button>
                        <button disabled={actionDisabled} onClick={() => handleAction(container.id, 'delete')}
                          className="p-2 bg-slate-800 text-slate-400 hover:bg-rose-500/20 hover:text-rose-400 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors" title="Elimina">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>

                  {/* Container header */}
                  <div className="mb-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className={cn(
                        "w-2.5 h-2.5 rounded-full",
                        isRunning ? "bg-emerald-500 shadow-[0_0_8px_theme(colors.emerald.500)]" :
                        isTransitioning ? "bg-amber-500 shadow-[0_0_8px_theme(colors.amber.500)] animate-pulse" :
                        "bg-slate-500"
                      )} />
                      <h3 className="text-lg font-semibold text-white truncate max-w-[220px]" title={container.name}>{container.name}</h3>
                      <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full font-medium",
                        isRunning ? "bg-emerald-500/10 text-emerald-400" :
                        isTransitioning ? "bg-amber-500/10 text-amber-400" :
                        "bg-slate-800 text-slate-400"
                      )}>
                        {container.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 font-mono truncate max-w-[300px]">{container.image}</p>
                    {svcInfo?.capabilities?.algorithm && (
                      <p className="text-xs text-indigo-400 mt-1">Algoritmo: {svcInfo.capabilities.algorithm}</p>
                    )}
                  </div>

                  {/* Info badges: Health, Port, Uptime, Mem Limit */}
                  {isRunning && (
                    <div className="flex flex-wrap gap-2 mb-4 text-xs">
                      <div className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1 rounded-lg border",
                        isHealthy ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                                  : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      )}>
                        {isHealthy ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                        {isHealthy ? 'Healthy' : 'Unhealthy'}
                      </div>
                      {activePort && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-slate-800/50 border-slate-700 text-slate-300">
                          <Globe className="w-3.5 h-3.5" /> localhost:{activePort}
                        </div>
                      )}
                      {cStats?.started_at && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-slate-800/50 border-slate-700 text-slate-300">
                          <Clock className="w-3.5 h-3.5" /> Uptime: <LiveUptime startedAt={cStats.started_at} />
                        </div>
                      )}
                      {cStats && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border bg-slate-800/50 border-slate-700 text-slate-300">
                          <MemoryStick className="w-3.5 h-3.5" />
                          {/* has_mem_limit viene dal backend che legge HostConfig.Memory:
                              0 = nessun limite esplicito, altrimenti il valore reale in bytes */}
                          Limit: {cStats.has_mem_limit && cStats.mem_limit_mb != null
                            ? `${cStats.mem_limit_mb.toFixed(0)} MB`
                            : 'No limit'}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Stats bars */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/50">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5"><Cpu className="w-3.5 h-3.5" /> CPU</span>
                        <span className="text-sm font-semibold text-slate-200">
                          {isRunning && cStats ? <SmoothNumber value={cStats.cpu_percent.toFixed(1)} suffix="%" /> : '--'}
                        </span>
                      </div>
                      <div className="w-full bg-slate-800/50 rounded-full h-1.5">
                        <div className="bg-blue-500 h-1.5 rounded-full transition-all duration-1000 ease-linear"
                          style={{ width: `${isRunning && cStats ? Math.min(cStats.cpu_percent, 100) : 0}%` }} />
                      </div>
                    </div>
                    <div className="bg-slate-950/50 rounded-xl p-4 border border-slate-800/50">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5"><MemoryStick className="w-3.5 h-3.5" /> RAM</span>
                        <span className="text-sm font-semibold text-slate-200">
                          {isRunning && cStats ? <SmoothNumber value={cStats.mem_usage_mb.toFixed(0)} suffix=" MB" /> : '--'}
                        </span>
                      </div>
                      <div className="w-full bg-slate-800/50 rounded-full h-1.5">
                        <div className="bg-indigo-500 h-1.5 rounded-full transition-all duration-1000 ease-linear"
                          style={{ width: `${isRunning && cStats ? Math.min(cStats.mem_percent, 100) : 0}%` }} />
                      </div>
                    </div>
                  </div>

                  {/* Inference section: solo per servizi CV che hanno classi di classificazione */}
                  {isRunning && supportsInference && (
                    <div className="border-t border-slate-800/50 pt-4">
                      <h4 className="text-xs font-medium text-slate-400 mb-3 flex items-center gap-1.5">
                        <ImageIcon className="w-3.5 h-3.5" /> Test Inferenza
                        {svcInfo?.capabilities?.classes && (
                          <span className="text-slate-500 ml-1">
                            ({svcInfo.capabilities.classes.join(', ')})
                          </span>
                        )}
                      </h4>
                      <div className="flex gap-4 items-start">
                        <label className="flex-shrink-0 w-24 h-24 rounded-xl border-2 border-dashed border-slate-700 hover:border-indigo-500 bg-slate-950/50 flex flex-col items-center justify-center cursor-pointer transition-colors group/upload relative overflow-hidden">
                          {infState?.previewUrl ? (
                            <img src={infState.previewUrl} alt="preview" className="w-full h-full object-cover rounded-lg" />
                          ) : (
                            <>
                              <Upload className="w-5 h-5 text-slate-500 group-hover/upload:text-indigo-400 transition-colors" />
                              <span className="text-[10px] text-slate-500 mt-1">Carica</span>
                            </>
                          )}
                          <input type="file" accept="image/*" className="hidden"
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleInference(container.id, file);
                              e.target.value = '';
                            }} />
                        </label>
                        <div className="flex-1 min-w-0">
                          {infState?.isLoading && (
                            <div className="flex items-center gap-2 text-sm text-slate-400">
                              <div className="w-4 h-4 border-2 border-slate-600 border-t-indigo-500 rounded-full animate-spin" />
                              Classificazione in corso...
                            </div>
                          )}
                          {infState?.result && (
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-lg">
                                  {infState.result.result}
                                </span>
                                <span className="text-xs text-slate-400">
                                  {(infState.result.confidence * 100).toFixed(1)}% confidence
                                </span>
                              </div>
                              <p className="text-xs text-slate-500">Latenza: {infState.result.latency_ms.toFixed(0)}ms</p>
                            </div>
                          )}
                          {infState?.error && <p className="text-xs text-rose-400">{infState.error}</p>}
                          {!infState && (
                            <p className="text-xs text-slate-500 mt-2">
                              Carica un'immagine per testare la classificazione.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Create Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsModalOpen(false)}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md relative z-10 shadow-2xl overflow-hidden">
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
                    onChange={e => setFormParams({ ...formParams, service_name: e.target.value.toLowerCase().replace(/\s+/g, '-') })} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">CPU Cores</label>
                    <input type="number" step="0.5" min="0.5" max="4"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      value={formParams.cpu_cores}
                      onChange={e => setFormParams({ ...formParams, cpu_cores: parseFloat(e.target.value) || 1.0 })} />
                    <p className="text-xs text-slate-500 mt-1">0.5 - 4.0 cores</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">RAM Limit (MB)</label>
                    <input type="number" step="128" min="128" max="4096"
                      className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      value={formParams.mem_limit_mb}
                      onChange={e => setFormParams({ ...formParams, mem_limit_mb: parseInt(e.target.value) || 512 })} />
                    <p className="text-xs text-slate-500 mt-1">128 - 4096 MB</p>
                  </div>
                </div>
                <div className="pt-4 flex gap-3">
                  <button type="button" onClick={() => setIsModalOpen(false)}
                    className="flex-1 px-4 py-3 border border-slate-700 text-slate-300 rounded-xl font-medium hover:bg-slate-800 transition-colors">
                    Annulla
                  </button>
                  <button type="submit" disabled={isSubmitting}
                    className="flex-1 px-4 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors shadow-lg shadow-indigo-500/20 flex justify-center items-center">
                    {isSubmitting ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : "Crea Template"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Logs Modal */}
      <AnimatePresence>
        {logsModalState.isOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setLogsModalState(prev => ({ ...prev, isOpen: false }))}
              className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl h-[70vh] flex flex-col relative z-10 shadow-2xl overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/50">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <TerminalSquare className="w-5 h-5 text-indigo-400" /> Logs Console
                  <span className="text-sm font-normal text-slate-400 ml-2">({logsModalState.containerName})</span>
                </h3>
                <button type="button" onClick={() => setLogsModalState(prev => ({ ...prev, isOpen: false }))} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>
              </div>
              <div className="p-4 flex-1 overflow-auto bg-[#0d1117]">
                {logsModalState.isLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
                  </div>
                ) : (
                  <pre className="text-sm font-mono text-emerald-400 whitespace-pre-wrap">{logsModalState.logs || "Nessun log disponibile."}</pre>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Toasts */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
        <AnimatePresence>
          {toasts.map(toast => <Toast key={toast.id} toast={toast} onClose={removeToast} />)}
        </AnimatePresence>
      </div>
    </div>
  );
}
