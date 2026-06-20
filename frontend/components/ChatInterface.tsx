"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Send,
  Phone,
  Brain,
  User,
  Loader2,
  AlertCircle,
  X,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Plus,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { BACKEND_URL, WS_URL } from "@/lib/utils";

const PHONE_NUMBER =
  process.env.NEXT_PUBLIC_VAPI_PHONE_NUMBER || "+1 (800) AGENT-VX";
const STORAGE_KEY = "agentvoxa.chat.threads";

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  escalated?: boolean;
};

type StoredMessage = Omit<Message, "timestamp"> & { timestamp: string };

type ContactInfo = {
  name: string;
  email: string;
  phone: string;
};

type ConversationThread = {
  sessionId: string;
  title: string;
  summary: string;
  updatedAt: string;
  messages: StoredMessage[];
  contactInfo: ContactInfo;
};

type BrowserSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  start: () => void;
  stop: () => void;
};

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
    SpeechRecognition?: new () => BrowserSpeechRecognition;
  }
}

const createWelcomeMessage = (): Message => ({
  id: "welcome",
  role: "agent",
  content:
    "Hello, I am AgentVoxa. Ask anything about courses, admissions, scholarships, and campus life.",
  timestamp: new Date(),
});

const emptyContact: ContactInfo = { name: "", email: "", phone: "" };

const parseStoredMessage = (message: StoredMessage): Message => ({
  ...message,
  timestamp: new Date(message.timestamp),
});

const toStoredMessage = (message: Message): StoredMessage => ({
  ...message,
  timestamp: message.timestamp.toISOString(),
});

function renderInteractiveAsteriskText(
  text: string,
  onTokenClick: (token: string) => void,
): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return parts.map((part, index) => {
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
    const inlineMatch = part.match(/^\*([^*]+)\*$/);
    const token = boldMatch?.[1] || inlineMatch?.[1];

    if (!token) {
      return (
        <span key={`text-${index}`} className="whitespace-pre-wrap">
          {part}
        </span>
      );
    }

    return (
      <button
        key={`token-${index}`}
        type="button"
        onClick={() => onTokenClick(token)}
        className="mx-0.5 inline-flex items-center rounded-md bg-brand-yellow/25 px-1.5 py-0.5 font-semibold text-brand-blue underline-offset-2 transition hover:scale-[1.03] hover:bg-brand-yellow/40 hover:underline"
        title="Tap to reuse this phrase"
      >
        {token}
      </button>
    );
  });
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMounted, setHasMounted] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [threads, setThreads] = useState<ConversationThread[]>([]);
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactInfo, setContactInfo] = useState<ContactInfo>(emptyContact);
  const [isListening, setIsListening] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(true);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const autoSpeakRef = useRef(autoSpeak);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    autoSpeakRef.current = autoSpeak;
    if (!autoSpeak) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    }
  }, [autoSpeak]);

  const persistThreads = useCallback((nextThreads: ConversationThread[]) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextThreads));
  }, []);

  const createNewConversation = useCallback(() => {
    const nextSessionId = crypto.randomUUID();
    const nextMessages = [createWelcomeMessage()];
    const thread: ConversationThread = {
      sessionId: nextSessionId,
      title: "New conversation",
      summary: "Start asking your question",
      updatedAt: new Date().toISOString(),
      messages: nextMessages.map(toStoredMessage),
      contactInfo: emptyContact,
    };

    setCurrentSessionId(nextSessionId);
    setMessages(nextMessages);
    setContactInfo(emptyContact);
    setShowContactForm(false);
    setThreads((prev) => {
      const next = [thread, ...prev];
      persistThreads(next);
      return next;
    });
  }, [persistThreads]);

  const speakText = useCallback(async (text: string) => {
    if (typeof window === "undefined" || !autoSpeakRef.current) return;
    
    if (audioRef.current) {
      audioRef.current.pause();
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    
    const url = `${BACKEND_URL}/api/chat/tts?text=${encodeURIComponent(text)}`;
    try {
      const audio = new Audio(url);
      audioRef.current = audio;
      
      audio.onerror = () => {
        console.warn("ElevenLabs TTS failed (likely 401/Invalid Key), falling back to browser TTS");
        const utter = new SpeechSynthesisUtterance(text);
        window.speechSynthesis.speak(utter);
      };

      await audio.play();
    } catch (e) {
      console.warn("Audio play prevented, falling back to browser TTS", e);
      const utter = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utter);
    }
  }, []);

  useEffect(() => {
    setHasMounted(true);
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      createNewConversation();
      return;
    }

    try {
      const parsed = JSON.parse(raw) as ConversationThread[];
      if (!parsed.length) {
        createNewConversation();
        return;
      }

      const sorted = parsed.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
      const active = sorted[0];
      setThreads(sorted);
      setCurrentSessionId(active.sessionId);
      setMessages(active.messages.map(parseStoredMessage));
      setContactInfo(active.contactInfo || emptyContact);
    } catch {
      createNewConversation();
    }
  }, [createNewConversation]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!currentSessionId || messages.length === 0) return;

    setThreads((prev) => {
      const latestUser = [...messages].reverse().find((msg) => msg.role === "user");
      const latestAgent = [...messages].reverse().find((msg) => msg.role === "agent");
      const title = latestUser?.content.slice(0, 42) || "New conversation";
      const summary = (latestAgent?.content || latestUser?.content || "").slice(0, 100) || "No messages yet";
      const updatedAt = new Date().toISOString();
      const nextThread: ConversationThread = {
        sessionId: currentSessionId,
        title,
        summary,
        updatedAt,
        messages: messages.map(toStoredMessage),
        contactInfo,
      };

      const existingIndex = prev.findIndex((thread) => thread.sessionId === currentSessionId);
      const merged = existingIndex === -1
        ? [nextThread, ...prev]
        : [
            nextThread,
            ...prev.filter((thread) => thread.sessionId !== currentSessionId),
          ];

      persistThreads(merged);
      return merged;
    });
  }, [messages, currentSessionId, contactInfo, persistThreads]);

  const connectWS = useCallback(() => {
    if (!shouldReconnectRef.current) return;

    const ws = new WebSocket(`${WS_URL}/api/chat/ws`);

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error) return;

      const agentMsg: Message = {
        id: crypto.randomUUID(),
        role: "agent",
        content: data.answer,
        timestamp: new Date(),
        escalated: data.escalate_to_human,
      };

      setMessages((prev) => [...prev, agentMsg]);
      setLoading(false);

      if (autoSpeakRef.current) {
        speakText(data.answer);
      }

      if (data.admission_interest && !contactInfo.name && !contactInfo.email && !contactInfo.phone) {
        setShowContactForm(true);
      }

      if (data.captured_data && Object.keys(data.captured_data).length > 0) {
        setContactInfo((prev) => ({ ...prev, ...data.captured_data }));
        setShowContactForm(false);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (shouldReconnectRef.current) {
        reconnectTimerRef.current = setTimeout(connectWS, 3000);
      }
    };

    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [speakText]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connectWS();

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      const ws = wsRef.current;
      if (!ws) return;

      if (ws.readyState === WebSocket.CONNECTING) {
        ws.onopen = () => ws.close(1000, "component unmounted");
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        return;
      }

      if (ws.readyState === WebSocket.OPEN) {
        ws.close(1000, "component unmounted");
      }
    };
  }, [connectWS]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) return;

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .trim();
      setInput(transcript);
    };

    recognitionRef.current = recognition;
    return () => {
      recognition.stop();
      recognitionRef.current = null;
    };
  }, []);

  const sendMessageFallback = async (payload: {
    message: string;
    session_id: string;
    contact_name?: string;
    contact_email?: string;
    contact_phone?: string;
  }) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      const responseMessage: Message = {
        id: crypto.randomUUID(),
        role: "agent",
        content: data.answer,
        timestamp: new Date(),
        escalated: data.escalate_to_human,
      };
      setMessages((prev) => [...prev, responseMessage]);
      if (autoSpeakRef.current) {
        speakText(data.answer);
      }
      if (data.admission_interest && !contactInfo.name && !contactInfo.email && !contactInfo.phone) {
        setShowContactForm(true);
      }
      if (data.captured_data && Object.keys(data.captured_data).length > 0) {
        setContactInfo((prev) => ({ ...prev, ...data.captured_data }));
        setShowContactForm(false);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: "Sorry, I am having trouble connecting right now. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading || !currentSessionId) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const payload = {
      message: text,
      session_id: currentSessionId,
      ...(contactInfo.name && { contact_name: contactInfo.name }),
      ...(contactInfo.email && { contact_email: contactInfo.email }),
      ...(contactInfo.phone && { contact_phone: contactInfo.phone }),
    };

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
      return;
    }

    await sendMessageFallback(payload);
  };

  const saveContactDetails = async () => {
    if (!currentSessionId) return;
    if (!contactInfo.name && !contactInfo.email && !contactInfo.phone) return;

    const contactLine = [contactInfo.name, contactInfo.email, contactInfo.phone]
      .filter(Boolean)
      .join(" | ");

    const note: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: `Shared contact details: ${contactLine}`,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, note]);

    try {
      await fetch(`${BACKEND_URL}/api/chat/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: currentSessionId,
          ...(contactInfo.name && { contact_name: contactInfo.name }),
          ...(contactInfo.email && { contact_email: contactInfo.email }),
          ...(contactInfo.phone && { contact_phone: contactInfo.phone }),
        }),
      });

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: "Thanks, your details are captured for follow-up.",
          timestamp: new Date(),
        },
      ]);
      setShowContactForm(false);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "agent",
          content: "I could not save those details yet. Please send a message so I can retain them.",
          timestamp: new Date(),
        },
      ]);
    }
  };

  const startListening = () => recognitionRef.current?.start();
  const stopListening = () => recognitionRef.current?.stop();

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const selectThread = (thread: ConversationThread) => {
    setCurrentSessionId(thread.sessionId);
    setMessages(thread.messages.map(parseStoredMessage));
    setContactInfo(thread.contactInfo || emptyContact);
  };

  const applyAsteriskToken = (token: string) => {
    setInput((prev) => (prev ? `${prev} ${token}` : token));
  };

  return (
    <div className="relative h-screen overflow-hidden bg-gradient-to-br from-[#FFF3E8] via-[#F8FBFF] to-[#FFE5E7]">
      <div className="pointer-events-none absolute -left-32 top-8 h-72 w-72 rounded-full bg-brand-yellow/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 bottom-20 h-80 w-80 rounded-full bg-brand-red/15 blur-3xl" />

      <div className="relative z-10 flex h-screen">
        <aside className="hidden w-80 border-r border-white/40 bg-white/55 backdrop-blur-xl md:flex md:flex-col">
          <div className="border-b border-white/60 px-5 py-4">
            <Link href="/" className="mb-4 flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-red shadow-lg shadow-brand-red/35">
                <Brain className="h-5 w-5 text-white" />
              </div>
              <span className="font-semibold text-brand-blue">
                Agent<span className="text-brand-red">Voxa</span>
              </span>
            </Link>

            <button
              onClick={createNewConversation}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand-blue px-3 py-2.5 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-[#152947]"
            >
              <Plus className="h-4 w-4" />
              New Conversation
            </button>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto px-3 py-4">
            {threads.map((thread) => {
              const active = thread.sessionId === currentSessionId;
              return (
                <button
                  key={thread.sessionId}
                  onClick={() => selectThread(thread)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    active
                      ? "border-brand-blue/35 bg-brand-blue/10 shadow-sm"
                      : "border-white/50 bg-white/70 hover:border-brand-blue/20 hover:bg-white"
                  }`}
                >
                  <p className="truncate text-sm font-semibold text-gray-800">{thread.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-gray-500">{thread.summary}</p>
                  <p className="mt-2 text-[11px] text-gray-400">
                    {new Date(thread.updatedAt).toLocaleString()}
                  </p>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="flex flex-1 flex-col">
          <header className="border-b border-white/50 bg-white/60 px-4 py-3 backdrop-blur-xl md:px-6">
            <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-red shadow-lg shadow-brand-red/30">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">Live Assistant</p>
                  <p className="text-xs text-gray-500">Session: {currentSessionId.slice(0, 8) || "--------"}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={createNewConversation}
                  className="hidden items-center gap-1.5 rounded-full border border-red-500/20 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-100 sm:flex"
                  title="Clear chat and start over"
                >
                  <X className="h-4 w-4" />
                  Clear Chat
                </button>
                <a
                  href={`tel:${PHONE_NUMBER}`}
                  className="hidden items-center gap-1.5 rounded-full border border-brand-blue/20 bg-white/70 px-3 py-1.5 text-sm font-medium text-brand-blue transition hover:bg-white sm:flex"
                >
                  <Phone className="h-4 w-4" />
                  {PHONE_NUMBER}
                </a>
                <div
                  className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-emerald-500" : "bg-gray-300"}`}
                  title={connected ? "Connected" : "Connecting..."}
                />
              </div>
            </div>
          </header>

          <AnimatePresence>
            {showContactForm && (
              <motion.div
                initial={{ y: -10, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -10, opacity: 0 }}
                className="border-b border-brand-yellow/35 bg-brand-yellow/20 px-4 py-3"
              >
                <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 lg:flex-row lg:items-center">
                  <p className="text-sm font-semibold text-gray-700">Share your details for admission follow-up:</p>
                  <input
                    type="text"
                    placeholder="Name"
                    value={contactInfo.name}
                    onChange={(e) => setContactInfo((c) => ({ ...c, name: e.target.value }))}
                    className="rounded-xl border border-white/70 bg-white/85 px-3 py-2 text-sm outline-none ring-brand-red/35 transition focus:ring-2"
                  />
                  <input
                    type="email"
                    placeholder="Email"
                    value={contactInfo.email}
                    onChange={(e) => setContactInfo((c) => ({ ...c, email: e.target.value }))}
                    className="rounded-xl border border-white/70 bg-white/85 px-3 py-2 text-sm outline-none ring-brand-red/35 transition focus:ring-2"
                  />
                  <input
                    type="tel"
                    placeholder="Phone"
                    value={contactInfo.phone}
                    onChange={(e) => setContactInfo((c) => ({ ...c, phone: e.target.value }))}
                    className="rounded-xl border border-white/70 bg-white/85 px-3 py-2 text-sm outline-none ring-brand-red/35 transition focus:ring-2"
                  />
                  <button
                    onClick={saveContactDetails}
                    className="rounded-xl bg-brand-red px-3 py-2 text-sm font-medium text-white transition hover:bg-red-700"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setShowContactForm(false)}
                    className="self-end text-gray-500 transition hover:text-gray-700 lg:self-center"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex-1 overflow-y-auto px-4 py-6 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-brand-blue/20 hover:scrollbar-thumb-brand-blue/40">
            <div className="mx-auto w-full max-w-5xl space-y-4">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12, scale: 0.99 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 4 }}
                    transition={{ duration: 0.22 }}
                    className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                  >
                    <div
                      className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full shadow-sm ${
                        msg.role === "agent" ? "bg-brand-red" : "bg-brand-blue"
                      }`}
                    >
                      {msg.role === "agent" ? (
                        <Brain className="h-4 w-4 text-white" />
                      ) : (
                        <User className="h-4 w-4 text-white" />
                      )}
                    </div>

                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                        msg.role === "user"
                          ? "rounded-tr-sm bg-brand-blue text-white"
                          : "rounded-tl-sm border border-white/70 bg-white/85 text-gray-800"
                      }`}
                    >
                      <div className="break-words">
                        {renderInteractiveAsteriskText(msg.content, applyAsteriskToken)}
                      </div>

                      {msg.escalated && (
                        <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-yellow-700">
                          <AlertCircle className="h-3.5 w-3.5" />
                          Transferred to human support
                        </div>
                      )}

                      <p
                        className={`mt-1 text-xs ${msg.role === "user" ? "text-blue-200" : "text-gray-400"}`}
                        suppressHydrationWarning
                      >
                        {hasMounted
                          ? msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                          : "--:--"}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {loading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-red">
                    <Brain className="h-4 w-4 text-white" />
                  </div>
                  <div className="rounded-2xl rounded-tl-sm border border-white/70 bg-white/85 px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-brand-red" />
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="border-t border-white/50 bg-white/60 px-4 py-4 backdrop-blur-xl">
            <div className="mx-auto flex w-full max-w-5xl items-end gap-3">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about admissions, fee structure, placements, or scholarships"
                rows={1}
                className="min-h-[52px] flex-1 resize-none rounded-2xl border border-white/70 bg-white/90 px-4 py-3 text-sm outline-none ring-brand-red/35 transition focus:ring-2"
              />

              <div className="flex items-center gap-2">
                <button
                  onClick={isListening ? stopListening : startListening}
                  className={`rounded-xl p-3 transition ${
                    isListening
                      ? "bg-red-100 text-red-700 hover:bg-red-200"
                      : "bg-white text-brand-blue hover:bg-blue-50"
                  }`}
                  title={isListening ? "Stop voice input" : "Start voice input"}
                >
                  {isListening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                </button>

                <button
                  onClick={() => setAutoSpeak((prev) => !prev)}
                  className={`rounded-xl p-3 transition ${
                    autoSpeak
                      ? "bg-brand-yellow/30 text-brand-blue hover:bg-brand-yellow/45"
                      : "bg-white text-gray-500 hover:bg-gray-100"
                  }`}
                  title={autoSpeak ? "Disable text-to-speech" : "Enable text-to-speech"}
                >
                  {autoSpeak ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5" />}
                </button>

                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                  className="rounded-xl bg-brand-red p-3 text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Send className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
