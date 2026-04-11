"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Phone, Brain, User, Loader2, AlertCircle, X } from "lucide-react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { WS_URL, BACKEND_URL } from "@/lib/utils";

const PHONE_NUMBER = process.env.NEXT_PUBLIC_EXOTEL_PHONE_NUMBER || "+1 (800) AGENT-VX";

type Message = {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: Date;
  escalated?: boolean;
};

type ContactInfo = {
  name: string;
  email: string;
  phone: string;
};

export default function ChatInterface() {
  const { data: session } = useSession();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "agent",
      content:
        "👋 Hello! I'm AgentVoxa, your AI receptionist. How can I help you today? Feel free to ask about courses, admissions, fees, or campus life.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMounted, setHasMounted] = useState(false);
  const [connected, setConnected] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactInfo, setContactInfo] = useState<ContactInfo>({
    name: "",
    email: "",
    phone: "",
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    setHasMounted(true);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // WebSocket connection
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

      if (data.admission_interest && !showContactForm) {
        setShowContactForm(true);
      }
    };

    ws.onclose = () => {
      setConnected(false);

      // Auto-reconnect after 3s only while component is mounted.
      if (shouldReconnectRef.current) {
        reconnectTimerRef.current = setTimeout(connectWS, 3000);
      }
    };

    ws.onerror = () => ws.close();

    wsRef.current = ws;
  }, [showContactForm]);

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

      // In React Strict Mode, cleanup can run while socket is still CONNECTING.
      // Avoid noisy browser warning by waiting until open before closing.
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
    // connectWS is stable (useCallback) – run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

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
      session_id: sessionId,
      ...(contactInfo.name && { contact_name: contactInfo.name }),
      ...(contactInfo.email && { contact_email: contactInfo.email }),
      ...(contactInfo.phone && { contact_phone: contactInfo.phone }),
    };

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    } else {
      // Fallback to REST
      try {
        const res = await fetch(`${BACKEND_URL}/api/chat/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "agent",
            content: data.answer,
            timestamp: new Date(),
            escalated: data.escalate_to_human,
          },
        ]);
        if (data.admission_interest) setShowContactForm(true);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "agent",
            content: "Sorry, I'm having trouble connecting. Please try again.",
            timestamp: new Date(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between shadow-sm">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-brand-red rounded-lg flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <span className="font-bold text-gray-900">
            Agent<span className="text-brand-red">Voxa</span>
          </span>
        </Link>

        <div className="flex items-center gap-3">
          <a
            href={`tel:${PHONE_NUMBER}`}
            className="flex items-center gap-1.5 text-sm text-brand-blue font-medium hover:underline"
          >
            <Phone className="w-4 h-4" />
            {PHONE_NUMBER}
          </a>
          <div
            className={`w-2 h-2 rounded-full ${
              connected ? "bg-green-500" : "bg-gray-300"
            }`}
            title={connected ? "Connected" : "Connecting..."}
          />
        </div>
      </header>

      {/* Contact info collection banner */}
      <AnimatePresence>
        {showContactForm && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="bg-brand-yellow/20 border-b border-yellow-300 px-4 py-3"
          >
            <div className="container mx-auto max-w-3xl flex flex-col sm:flex-row gap-3 items-end">
              <p className="text-sm font-medium text-gray-700 whitespace-nowrap">
                📋 Share your contact info:
              </p>
              <input
                type="text"
                placeholder="Your name"
                value={contactInfo.name}
                onChange={(e) =>
                  setContactInfo((c) => ({ ...c, name: e.target.value }))
                }
                className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-red"
              />
              <input
                type="email"
                placeholder="Email"
                value={contactInfo.email}
                onChange={(e) =>
                  setContactInfo((c) => ({ ...c, email: e.target.value }))
                }
                className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-red"
              />
              <input
                type="tel"
                placeholder="Phone"
                value={contactInfo.phone}
                onChange={(e) =>
                  setContactInfo((c) => ({ ...c, phone: e.target.value }))
                }
                className="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-red"
              />
              <button
                onClick={() => setShowContactForm(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="container mx-auto max-w-3xl space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex gap-3 ${
                  msg.role === "user" ? "flex-row-reverse" : "flex-row"
                }`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                    msg.role === "agent"
                      ? "bg-brand-red"
                      : "bg-brand-blue"
                  }`}
                >
                  {msg.role === "agent" ? (
                    <Brain className="w-4 h-4 text-white" />
                  ) : (
                    <User className="w-4 h-4 text-white" />
                  )}
                </div>

                {/* Bubble */}
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-brand-blue text-white rounded-tr-sm"
                      : "bg-white text-gray-800 shadow-sm border border-gray-100 rounded-tl-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.escalated && (
                    <div className="mt-2 flex items-center gap-1.5 text-yellow-600 text-xs font-medium">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Transferred to human staff
                    </div>
                  )}
                  <p
                    className={`text-xs mt-1 ${
                      msg.role === "user" ? "text-blue-200" : "text-gray-400"
                    }`}
                    suppressHydrationWarning
                  >
                    {hasMounted
                      ? msg.timestamp.toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "--:--"}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex gap-3"
            >
              <div className="w-8 h-8 rounded-full bg-brand-red flex items-center justify-center">
                <Brain className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-gray-100">
                <Loader2 className="w-4 h-4 text-brand-red animate-spin" />
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-4 py-4">
        <div className="container mx-auto max-w-3xl flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything about courses, admissions, or campus life…"
            rows={1}
            className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-red focus:border-transparent transition"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            className="bg-brand-red hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white p-3 rounded-xl transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
