"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Upload,
  Trash2,
  FileText,
  MessageSquare,
  Phone,
  Users,
  BarChart3,
  LogOut,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { BACKEND_URL } from "@/lib/utils";

type Tab = "knowledge-base" | "chat-logs" | "call-logs" | "insights" | "stats";

type Document = {
  id: number;
  original_name: string;
  status: string;
  chunk_count: number;
  size_bytes: number;
  created_at: string;
};

type ChatLogEntry = {
  id: number;
  session_id: string;
  user_message: string;
  agent_response: string;
  admission_interest: string;
  escalated_to_human: boolean;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  created_at: string;
};

type CallLogEntry = {
  id: number;
  vonage_call_uuid: string;
  caller_number: string | null;
  transcript: string | null;
  call_status: string;
  admission_interest: string;
  escalated_to_human: boolean;
  started_at: string;
  ended_at: string | null;
};

type InterestedUser = {
  session_id: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  sample_message: string;
  created_at: string;
};

type Stats = {
  total_chats: number;
  total_calls: number;
  interested_in_admission: number;
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AdminDashboard() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("knowledge-base");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [chatLogs, setChatLogs] = useState<ChatLogEntry[]>([]);
  const [callLogs, setCallLogs] = useState<CallLogEntry[]>([]);
  const [interestedUsers, setInterestedUsers] = useState<InterestedUser[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  // Auth guard
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    } else if (
      status === "authenticated" &&
      (session?.user as any)?.role !== "admin"
    ) {
      toast.error("Admin access required.");
      router.push("/");
    }
  }, [status, session, router]);

  const getHeaders = () => ({
    Authorization: `Bearer ${(session?.user as any)?.accessToken}`,
  });

  const fetchDocuments = async () => {
    setLoadingData(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/`, {
        headers: getHeaders(),
      });
      if (res.ok) setDocuments(await res.json());
    } catch {
      toast.error("Failed to load documents");
    } finally {
      setLoadingData(false);
    }
  };

  const fetchChatLogs = async () => {
    setLoadingData(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/chat-logs`, {
        headers: getHeaders(),
      });
      if (res.ok) setChatLogs(await res.json());
    } catch {
      toast.error("Failed to load chat logs");
    } finally {
      setLoadingData(false);
    }
  };

  const fetchCallLogs = async () => {
    setLoadingData(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/call-logs`, {
        headers: getHeaders(),
      });
      if (res.ok) setCallLogs(await res.json());
    } catch {
      toast.error("Failed to load call logs");
    } finally {
      setLoadingData(false);
    }
  };

  const fetchInsights = async () => {
    setLoadingData(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/interested-users`, {
        headers: getHeaders(),
      });
      if (res.ok) setInterestedUsers(await res.json());
    } catch {
      toast.error("Failed to load insights");
    } finally {
      setLoadingData(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/stats`, {
        headers: getHeaders(),
      });
      if (res.ok) setStats(await res.json());
    } catch {}
  };

  useEffect(() => {
    if (status !== "authenticated") return;
    fetchStats();
    if (activeTab === "knowledge-base") fetchDocuments();
    else if (activeTab === "chat-logs") fetchChatLogs();
    else if (activeTab === "call-logs") fetchCallLogs();
    else if (activeTab === "insights") fetchInsights();
    // Fetch functions are defined inline and depend on session/activeTab via closure;
    // they are intentionally excluded to avoid infinite re-render loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, status]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/upload`, {
        method: "POST",
        headers: getHeaders(),
        body: formData,
      });
      if (res.ok) {
        toast.success("Document uploaded and processed!");
        fetchDocuments();
      } else {
        const err = await res.json();
        toast.error(err.detail || "Upload failed");
      }
    } catch {
      toast.error("Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"?`)) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/${id}`, {
        method: "DELETE",
        headers: getHeaders(),
      });
      if (res.ok) {
        toast.success("Document deleted");
        setDocuments((prev) => prev.filter((d) => d.id !== id));
      }
    } catch {
      toast.error("Delete failed");
    }
  };

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: "knowledge-base", label: "Knowledge Base", icon: FileText },
    { id: "chat-logs", label: "Chat Logs", icon: MessageSquare },
    { id: "call-logs", label: "Call Logs", icon: Phone },
    { id: "insights", label: "Admission Insights", icon: Users },
    { id: "stats", label: "Stats", icon: BarChart3 },
  ];

  if (status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-red animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-brand-blue text-white flex flex-col">
        <div className="p-6 border-b border-white/10">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-brand-red rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg">
              Agent<span className="text-red-300">Voxa</span>
            </span>
          </Link>
          <p className="text-blue-200 text-xs mt-2">Admin Dashboard</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-white/15 text-white"
                  : "text-blue-200 hover:text-white hover:bg-white/10"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-white/10">
          <p className="text-blue-200 text-xs mb-3">
            {session?.user?.name}
          </p>
          <button
            onClick={() => signOut({ callbackUrl: "/" })}
            className="w-full flex items-center gap-2 text-sm text-blue-200 hover:text-white transition-colors px-4 py-2"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-8 py-5">
          <h1 className="text-xl font-bold text-gray-900">
            {tabs.find((t) => t.id === activeTab)?.label}
          </h1>
          {stats && (
            <div className="flex gap-6 mt-1">
              <span className="text-sm text-gray-500">
                {stats.total_chats} chats
              </span>
              <span className="text-sm text-gray-500">
                {stats.total_calls} calls
              </span>
              <span className="text-sm text-brand-red font-medium">
                {stats.interested_in_admission} admission leads
              </span>
            </div>
          )}
        </header>

        <div className="p-8">
          {/* ── Knowledge Base ── */}
          {activeTab === "knowledge-base" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              <div className="flex justify-between items-center">
                <p className="text-sm text-gray-500">
                  Upload PDF, DOCX, or Markdown files (max 50 MB).
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".pdf,.docx,.md,.txt"
                    className="hidden"
                    onChange={handleUpload}
                    disabled={uploading}
                  />
                  <span
                    className={`flex items-center gap-2 bg-brand-red text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-red-700 transition-colors ${
                      uploading ? "opacity-60 cursor-not-allowed" : ""
                    }`}
                  >
                    {uploading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Upload className="w-4 h-4" />
                    )}
                    {uploading ? "Processing…" : "Upload Document"}
                  </span>
                </label>
              </div>

              {loadingData ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-6 h-6 text-brand-red animate-spin" />
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>No documents uploaded yet.</p>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-100">
                      <tr>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Name</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Status</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Chunks</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Size</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Uploaded</th>
                        <th className="px-6 py-4"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {documents.map((doc) => (
                        <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                          <td className="px-6 py-4 font-medium text-gray-900">
                            {doc.original_name}
                          </td>
                          <td className="px-6 py-4">
                            <span
                              className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full ${
                                doc.status === "ready"
                                  ? "bg-green-50 text-green-700"
                                  : doc.status === "processing"
                                  ? "bg-yellow-50 text-yellow-700"
                                  : "bg-red-50 text-red-700"
                              }`}
                            >
                              {doc.status === "ready" ? (
                                <CheckCircle2 className="w-3 h-3" />
                              ) : doc.status === "processing" ? (
                                <Clock className="w-3 h-3" />
                              ) : (
                                <AlertCircle className="w-3 h-3" />
                              )}
                              {doc.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-gray-500">{doc.chunk_count}</td>
                          <td className="px-6 py-4 text-gray-500">{formatBytes(doc.size_bytes)}</td>
                          <td className="px-6 py-4 text-gray-400 text-xs">
                            {new Date(doc.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4">
                            <button
                              onClick={() => handleDelete(doc.id, doc.original_name)}
                              className="text-gray-400 hover:text-red-600 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </motion.div>
          )}

          {/* ── Chat Logs ── */}
          {activeTab === "chat-logs" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {loadingData ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-6 h-6 text-brand-red animate-spin" />
                </div>
              ) : chatLogs.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>No chat logs yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {chatLogs.map((log) => (
                    <div
                      key={log.id}
                      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5"
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400 font-mono">
                            {log.session_id.slice(0, 8)}…
                          </span>
                          {log.admission_interest === "high" && (
                            <span className="bg-brand-yellow/20 text-yellow-700 text-xs font-medium px-2 py-0.5 rounded-full">
                              Admission Interest
                            </span>
                          )}
                          {log.escalated_to_human && (
                            <span className="bg-red-50 text-red-700 text-xs font-medium px-2 py-0.5 rounded-full">
                              Escalated
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-gray-400">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 font-medium mb-1">
                        Q: {log.user_message}
                      </p>
                      <p className="text-sm text-gray-500 line-clamp-2">
                        A: {log.agent_response}
                      </p>
                      {(log.contact_name || log.contact_email) && (
                        <div className="mt-3 text-xs text-gray-500 bg-gray-50 rounded-lg p-3">
                          📋 {log.contact_name} · {log.contact_email} · {log.contact_phone}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ── Call Logs ── */}
          {activeTab === "call-logs" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {loadingData ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-6 h-6 text-brand-red animate-spin" />
                </div>
              ) : callLogs.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <Phone className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>No call logs yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {callLogs.map((log) => (
                    <div
                      key={log.id}
                      className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5"
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2">
                          <Phone className="w-4 h-4 text-brand-blue" />
                          <span className="font-medium text-gray-800 text-sm">
                            {log.caller_number || "Unknown"}
                          </span>
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                              log.call_status === "completed"
                                ? "bg-green-50 text-green-700"
                                : "bg-gray-50 text-gray-600"
                            }`}
                          >
                            {log.call_status}
                          </span>
                          {log.escalated_to_human && (
                            <span className="bg-red-50 text-red-700 text-xs font-medium px-2 py-0.5 rounded-full">
                              Transferred
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-gray-400">
                          {new Date(log.started_at).toLocaleString()}
                        </span>
                      </div>
                      {log.transcript && (
                        <p className="text-xs text-gray-500 line-clamp-3 font-mono bg-gray-50 rounded-lg p-3 mt-2">
                          {log.transcript}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {/* ── Admission Insights ── */}
          {activeTab === "insights" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <p className="text-sm text-gray-500 mb-6">
                Users who expressed interest in admission through chat.
              </p>
              {loadingData ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-6 h-6 text-brand-red animate-spin" />
                </div>
              ) : interestedUsers.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <Users className="w-12 h-12 mx-auto mb-3 opacity-40" />
                  <p>No admission leads yet.</p>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-100">
                      <tr>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Name</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Email</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Phone</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Query</th>
                        <th className="text-left px-6 py-4 font-semibold text-gray-700">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {interestedUsers.map((u, i) => (
                        <tr key={i} className="hover:bg-gray-50 transition-colors">
                          <td className="px-6 py-4 font-medium text-gray-900">
                            {u.contact_name || "—"}
                          </td>
                          <td className="px-6 py-4 text-brand-blue">
                            {u.contact_email || "—"}
                          </td>
                          <td className="px-6 py-4 text-gray-600">
                            {u.contact_phone || "—"}
                          </td>
                          <td className="px-6 py-4 text-gray-500 max-w-xs truncate">
                            {u.sample_message}
                          </td>
                          <td className="px-6 py-4 text-gray-400 text-xs">
                            {new Date(u.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </motion.div>
          )}

          {/* ── Stats ── */}
          {activeTab === "stats" && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid grid-cols-1 md:grid-cols-3 gap-6"
            >
              {[
                {
                  label: "Total Chats",
                  value: stats?.total_chats ?? "—",
                  icon: MessageSquare,
                  color: "text-brand-blue",
                  bg: "bg-blue-50",
                },
                {
                  label: "Total Calls",
                  value: stats?.total_calls ?? "—",
                  icon: Phone,
                  color: "text-brand-red",
                  bg: "bg-red-50",
                },
                {
                  label: "Admission Leads",
                  value: stats?.interested_in_admission ?? "—",
                  icon: Users,
                  color: "text-yellow-600",
                  bg: "bg-yellow-50",
                },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6"
                >
                  <div
                    className={`w-12 h-12 ${stat.bg} rounded-xl flex items-center justify-center mb-4`}
                  >
                    <stat.icon className={`w-6 h-6 ${stat.color}`} />
                  </div>
                  <p className="text-3xl font-bold text-gray-900 mb-1">
                    {stat.value}
                  </p>
                  <p className="text-sm text-gray-500">{stat.label}</p>
                </div>
              ))}
            </motion.div>
          )}
        </div>
      </main>
    </div>
  );
}
