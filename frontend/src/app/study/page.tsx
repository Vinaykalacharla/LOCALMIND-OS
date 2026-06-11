"use client";

import { useState, useEffect } from "react";
import { 
  getDueReviews, submitReview, generateExam, getExams, submitExam,
  StudyReview, StudyExam 
} from "@/lib/api";

export default function StudyPage() {
  const [activeTab, setActiveTab] = useState<"review" | "exam">("review");
  const [loading, setLoading] = useState(false);

  // Review State
  const [dueReviews, setDueReviews] = useState<StudyReview[]>([]);
  const [showAnswer, setShowAnswer] = useState(false);

  // Exam State
  const [exams, setExams] = useState<StudyExam[]>([]);
  const [examTopic, setExamTopic] = useState("");
  const [activeExam, setActiveExam] = useState<StudyExam | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    if (activeTab === "review") {
      fetchReviews();
    } else {
      fetchAllExams();
    }
  }, [activeTab]);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      const res = await getDueReviews();
      setDueReviews(res.due_reviews);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setShowAnswer(false);
    }
  };

  const fetchAllExams = async () => {
    try {
      setLoading(true);
      const res = await getExams();
      setExams(res.exams);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (quality: number) => {
    if (dueReviews.length === 0) return;
    const current = dueReviews[0];
    try {
      await submitReview(current.chunk_id, quality);
      setDueReviews(prev => prev.slice(1));
      setShowAnswer(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleGenerateExam = async () => {
    if (!examTopic.trim()) return;
    try {
      setLoading(true);
      const newExam = await generateExam(examTopic, 5);
      setExams(prev => [...prev, newExam]);
      setExamTopic("");
    } catch (e) {
      console.error(e);
      alert("Failed to generate exam. Check logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitExam = async () => {
    if (!activeExam) return;
    try {
      setLoading(true);
      const graded = await submitExam(activeExam.id, answers);
      setActiveExam(null);
      setAnswers({});
      fetchAllExams();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 pb-10">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-3xl border border-[var(--line)] bg-[var(--panel-main)] p-8 sm:p-12 shadow-panel backdrop-blur-xl">
        <div className="absolute top-0 right-0 -mt-16 -mr-16 h-64 w-64 rounded-full bg-[var(--success)] opacity-10 blur-[80px]"></div>
        <div className="absolute bottom-0 left-0 -mb-16 -ml-16 h-48 w-48 rounded-full bg-[var(--warning)] opacity-10 blur-[60px]"></div>
        
        <div className="relative z-10 max-w-3xl">
          <div className="eyebrow mb-2 inline-block rounded-full bg-[var(--success-dim)] px-3 py-1 border border-[var(--success)]/20 text-[var(--success)]">Learning Engine</div>
          <h2 className="mt-4 font-display text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 sm:text-5xl tracking-tight">
            Master your knowledge.
          </h2>
          <p className="mt-5 text-base leading-relaxed text-[var(--text-muted)] sm:text-lg max-w-2xl">
            Leverage Spaced Repetition and AI-generated Exam Simulations to cement your understanding of the indexed documents.
          </p>
        </div>
      </section>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--line)] pb-4">
        <button
          onClick={() => setActiveTab("review")}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${activeTab === 'review' ? 'bg-[var(--accent-dim)] text-[var(--accent-bright)] border border-[var(--accent)]/30' : 'text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--panel-hover)]'}`}
        >
          Spaced Repetition
        </button>
        <button
          onClick={() => setActiveTab("exam")}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition ${activeTab === 'exam' ? 'bg-[var(--warning-dim)] text-[var(--warning)] border border-[var(--warning)]/30' : 'text-[var(--text-muted)] hover:text-[var(--text-main)] hover:bg-[var(--panel-hover)]'}`}
        >
          AI Exam Simulator
        </button>
      </div>

      {activeTab === "review" ? (
        <section className="glow-card p-8 animate-fade">
          <div className="flex items-center justify-between mb-8 border-b border-[var(--line)] pb-6">
            <div>
              <h3 className="font-display text-2xl font-bold text-[var(--text-main)]">Daily Review</h3>
              <p className="text-sm text-[var(--text-muted)] mt-1">Review chunks to strengthen your memory.</p>
            </div>
            <div className="flex h-16 w-16 items-center justify-center rounded-full border-4 border-[var(--success)] bg-[var(--success-dim)] text-xl font-bold text-[var(--success)] shadow-sm">
              {dueReviews.length}
            </div>
          </div>
          
          <div className="mx-auto max-w-2xl text-center py-6">
            {loading && <div className="text-[var(--text-muted)]">Loading...</div>}
            {!loading && dueReviews.length === 0 && (
              <div className="text-xl text-[var(--text-muted)] py-12">You're all caught up for today!</div>
            )}
            
            {!loading && dueReviews.length > 0 && (
              <div className="text-left bg-[var(--panel-soft)] border border-[var(--line)] rounded-xl p-6">
                <div className="text-[11px] font-semibold uppercase tracking-widest text-[var(--text-muted)] mb-4">
                  Source: {dueReviews[0].source_file}
                </div>
                
                {!showAnswer ? (
                  <div className="text-lg text-[var(--text-main)] mb-12 italic">
                    Think about this document chunk...
                  </div>
                ) : (
                  <div className="text-lg text-[var(--text-main)] mb-12 whitespace-pre-wrap">
                    {dueReviews[0].text}
                  </div>
                )}
                
                {!showAnswer ? (
                  <button onClick={() => setShowAnswer(true)} className="btn-primary w-full py-3">
                    Show Content
                  </button>
                ) : (
                  <div className="grid grid-cols-4 gap-2">
                    <button onClick={() => handleReview(1)} className="btn-secondary text-rose-400 border-rose-500/30 hover:bg-rose-500/10">Again</button>
                    <button onClick={() => handleReview(3)} className="btn-secondary text-orange-400 border-orange-500/30 hover:bg-orange-500/10">Hard</button>
                    <button onClick={() => handleReview(4)} className="btn-secondary text-green-400 border-green-500/30 hover:bg-green-500/10">Good</button>
                    <button onClick={() => handleReview(5)} className="btn-secondary text-blue-400 border-blue-500/30 hover:bg-blue-500/10">Easy</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      ) : (
        <section className="glow-card p-8 animate-fade border-[var(--warning-dim)]">
          {!activeExam ? (
            <>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 border-b border-[var(--line)] pb-6 gap-4">
                <div>
                  <h3 className="font-display text-2xl font-bold text-[var(--text-main)]">Exam Simulator</h3>
                  <p className="text-sm text-[var(--text-muted)] mt-1">Generate dynamic tests from your document vault.</p>
                </div>
                <div className="flex items-center gap-2">
                  <input 
                    type="text" 
                    placeholder="Topic (e.g. History)" 
                    value={examTopic} 
                    onChange={e => setExamTopic(e.target.value)}
                    className="input-field max-w-[200px]"
                  />
                  <button 
                    onClick={handleGenerateExam} 
                    disabled={loading || !examTopic.trim()}
                    className="btn-primary bg-gradient-to-r from-[var(--warning)] to-amber-600 border-amber-500 shadow-amber-900/20 px-6 disabled:opacity-50"
                  >
                    {loading ? "Generating..." : "Generate Exam"}
                  </button>
                </div>
              </div>

              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {exams.map((exam, i) => (
                  <div key={i} onClick={() => !exam.score && setActiveExam(exam)} className="rounded-xl border border-[var(--line)] bg-[var(--panel-soft)] p-5 hover:border-[var(--warning)]/50 transition cursor-pointer">
                    <div className="font-semibold text-[var(--text-main)] capitalize">{exam.topic}</div>
                    <div className="mt-4 flex items-center justify-between text-xs text-[var(--text-muted)]">
                      <span>{exam.questions.length} Questions</span>
                      <span className={exam.score ? 'text-[var(--success)] font-medium' : 'text-amber-500'}>
                        {exam.score || "Take Exam"}
                      </span>
                    </div>
                  </div>
                ))}
                {exams.length === 0 && !loading && (
                  <div className="col-span-full text-center text-[var(--text-muted)] py-10">
                    No exams generated yet. Type a topic and click Generate Exam.
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="animate-fade">
              <button onClick={() => setActiveExam(null)} className="text-sm text-[var(--text-muted)] hover:text-[var(--text-main)] mb-6 flex items-center gap-2">
                &larr; Back to Exams
              </button>
              <h3 className="font-display text-2xl font-bold text-[var(--text-main)] mb-6 capitalize">
                Exam: {activeExam.topic}
              </h3>
              
              <div className="space-y-8 mb-8">
                {activeExam.questions.map((q, idx) => (
                  <div key={idx} className="bg-[var(--panel-soft)] border border-[var(--line)] p-6 rounded-xl">
                    <p className="font-medium text-[var(--text-main)] mb-4">{idx + 1}. {q.question}</p>
                    <div className="space-y-3">
                      {q.options.map((opt, oIdx) => (
                        <label key={oIdx} className="flex items-start gap-3 cursor-pointer group">
                          <input 
                            type="radio" 
                            name={`q-${idx}`} 
                            value={opt}
                            checked={answers[q.question] === opt}
                            onChange={(e) => setAnswers(prev => ({ ...prev, [q.question]: e.target.value }))}
                            className="mt-1"
                          />
                          <span className="text-sm text-[var(--text-muted)] group-hover:text-[var(--text-main)]">{opt}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              
              <button onClick={handleSubmitExam} disabled={loading} className="btn-primary w-full py-3">
                {loading ? "Submitting..." : "Submit Exam"}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
