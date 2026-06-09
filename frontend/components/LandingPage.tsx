"use client";

import { motion } from "framer-motion";
import { Phone, MessageCircle, Brain, Shield, Zap, Users } from "lucide-react";
import Link from "next/link";
import { useSession } from "next-auth/react";

const PHONE_NUMBER =
  process.env.NEXT_PUBLIC_VAPI_PHONE_NUMBER || "+1 (800) AGENT-VX";

const features = [
  {
    icon: Brain,
    title: "AI-Powered Answers",
    description:
      "Gemini-powered agent with RAG retrieval over your knowledge base for accurate, context-aware responses.",
    color: "text-brand-red",
  },
  {
    icon: Phone,
    title: "Voice Calling",
    description:
      "Call our number and speak to the AI receptionist in real-time. Powered by Vapi.",
    color: "text-brand-blue",
  },
  {
    icon: MessageCircle,
    title: "Live Chat",
    description:
      "Chat directly on the website with instant, intelligent answers via WebSocket.",
    color: "text-brand-yellow",
  },
  {
    icon: Shield,
    title: "Smart Escalation",
    description:
      "When the AI can't help, it seamlessly transfers you to human staff – on call or chat.",
    color: "text-brand-red",
  },
  {
    icon: Zap,
    title: "Hybrid Search",
    description:
      "Vector + full-text search over uploaded documents for best-in-class retrieval accuracy.",
    color: "text-brand-blue",
  },
  {
    icon: Users,
    title: "Admission Insights",
    description:
      "Automatically identifies prospective students and surfaces their details in the admin panel.",
    color: "text-brand-yellow",
  },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" },
  }),
};

export default function LandingPage() {
  const { data: session } = useSession();

  return (
    <div className="min-h-screen bg-white text-gray-900">
      {/* ── Navigation ── */}
      <nav className="sticky top-0 z-50 bg-white/90 backdrop-blur-sm border-b border-gray-200 shadow-sm">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-2"
          >
            <div className="w-8 h-8 bg-brand-red rounded-lg flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">
              Agent<span className="text-brand-red">Voxa</span>
            </span>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4"
          >
            <Link
              href="/chat"
              className="text-sm font-medium text-gray-600 hover:text-brand-red transition-colors"
            >
              Chat
            </Link>
            {session ? (
              session.user && (session.user as any).role === "admin" ? (
                <Link
                  href="/admin"
                  className="bg-brand-blue text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-800 transition-colors"
                >
                  Admin Dashboard
                </Link>
              ) : (
                <Link
                  href="/chat"
                  className="bg-brand-red text-white text-sm px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
                >
                  Go to Chat
                </Link>
              )
            ) : (
              <Link
                href="/login"
                className="bg-brand-red text-white text-sm px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
              >
                Sign In
              </Link>
            )}
          </motion.div>
        </div>
      </nav>

      {/* ── Hero Section ── */}
      <section className="relative overflow-hidden bg-gradient-to-br from-white via-red-50 to-blue-50 py-24 px-4">
        {/* Background decoration */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-20 left-10 w-72 h-72 bg-brand-red/10 rounded-full blur-3xl" />
          <div className="absolute bottom-10 right-10 w-96 h-96 bg-brand-blue/10 rounded-full blur-3xl" />
        </div>

        <div className="container mx-auto text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 bg-brand-red/10 text-brand-red px-4 py-1.5 rounded-full text-sm font-medium mb-6"
          >
            <Zap className="w-4 h-4" />
            Powered by Gemini AI + Vapi
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            className="text-5xl md:text-7xl font-extrabold text-gray-900 mb-6 leading-tight"
          >
            Your AI
            <br />
            <span className="text-brand-red">Receptionist</span>
            <br />
            <span className="text-brand-blue">Never Sleeps</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.7, delay: 0.25 }}
            className="text-xl text-gray-500 max-w-2xl mx-auto mb-10"
          >
            AgentVoxa handles student queries 24/7 – via chat or phone call –
            using a knowledge base you control.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35 }}
            className="flex flex-col sm:flex-row gap-4 justify-center"
          >
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 bg-brand-red text-white px-8 py-4 rounded-xl font-semibold text-lg shadow-lg hover:bg-red-700 hover:shadow-xl transition-all duration-200"
            >
              <MessageCircle className="w-5 h-5" />
              Start Chatting
            </Link>
            <a
              href={`tel:${PHONE_NUMBER}`}
              className="inline-flex items-center gap-2 bg-white border-2 border-brand-blue text-brand-blue px-8 py-4 rounded-xl font-semibold text-lg shadow hover:bg-blue-50 transition-all duration-200"
            >
              <Phone className="w-5 h-5" />
              Call {PHONE_NUMBER}
            </a>
          </motion.div>
        </div>
      </section>

      {/* ── Phone CTA Banner ── */}
      <section className="bg-brand-blue text-white py-8 px-4">
        <div className="container mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="animate-pulse-ring bg-white/20 rounded-full p-3">
              <Phone className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-sm text-blue-200">Available 24/7 – Call us at</p>
              <p className="text-2xl font-bold">{PHONE_NUMBER}</p>
            </div>
          </div>
          <p className="text-blue-200 text-sm max-w-md text-center">
            Speak directly with our AI receptionist. Real-time voice, instant answers.
            Human staff available if needed.
          </p>
        </div>
      </section>

      {/* ── Features Grid ── */}
      <section className="py-24 px-4 bg-gray-50">
        <div className="container mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Everything you need
            </h2>
            <p className="text-gray-500 text-lg max-w-xl mx-auto">
              A complete AI receptionist platform built for modern educational institutions.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                custom={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
              >
                <div className={`w-12 h-12 rounded-xl bg-gray-50 flex items-center justify-center mb-4 ${feature.color}`}>
                  <feature.icon className="w-6 h-6" />
                </div>
                <h3 className="font-semibold text-gray-900 text-lg mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Chat Preview CTA ── */}
      <section className="py-24 px-4 bg-white">
        <div className="container mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="bg-gradient-to-r from-brand-red to-red-700 rounded-3xl p-12 text-white max-w-3xl mx-auto shadow-2xl"
          >
            <MessageCircle className="w-12 h-12 mx-auto mb-4 opacity-80" />
            <h2 className="text-3xl font-bold mb-4">Ready to chat?</h2>
            <p className="text-red-100 mb-8">
              Ask anything about courses, admissions, fees, or campus life.
            </p>
            <Link
              href="/chat"
              className="inline-block bg-white text-brand-red font-semibold px-8 py-4 rounded-xl hover:bg-gray-50 transition-colors shadow"
            >
              Open Chat →
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-gray-900 text-gray-400 py-10 px-4">
        <div className="container mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-brand-red" />
            <span className="text-white font-semibold">
              Agent<span className="text-brand-red">Voxa</span>
            </span>
          </div>
          <p className="text-sm">© {new Date().getFullYear()} AgentVoxa</p>
          <div className="flex gap-6 text-sm">
            <Link href="/chat" className="hover:text-white transition-colors">Chat</Link>
            <Link href="/login" className="hover:text-white transition-colors">Login</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
