import { formatErrorMessage } from "@/lib/format";

export interface IngestResponse {
  job_id: string;
}

export interface SecurityStatus {
  configured: boolean;
  unlocked: boolean;
}

export interface JobStatus {
  state: "processing" | "done" | "error";
  step: string;
  progress: number;
  message: string;
}

export interface StatsResponse {
  indexed_files: number;
  total_chunks: number;
  graph_nodes: number;
  last_index_time: string;
  chunking_version: string;
  reindex_recommended: boolean;
  embedding_model: string;
  embedding_mode: string;
  vector_backend: string;
  graph_mode: string;
  pdf_backend: string;
  llm_mode: string;
  feature_status: FeatureStatus[];
}

export interface InsightTopic {
  topic: string;
  count: number;
}

export interface InsightsResponse {
  most_searched_topics: InsightTopic[];
  not_revised_topics: string[];
  peak_activity: string;
  recent_queries: string[];
}

export interface SearchItem {
  chunk_id: string;
  score: number;
  preview: string;
  text: string;
  source_file: string;
  page_number: number | null;
  chunk_index: number;
  section_path: string[];
  block_kind: string;
}

export interface SearchResponse {
  results: SearchItem[];
}

export type ConfidenceLabel = "high" | "medium" | "low";
export type EvidenceStatus = "grounded" | "limited" | "insufficient";
export type AnswerMode = "answer" | "study_guide" | "flashcards" | "quiz";

export interface AskSource {
  citation: string;
  chunk_id: string;
  score: number;
  retrieval_score: number;
  text: string;
  source_file: string;
  page_number: number | null;
  section_path: string[];
  block_kind: string;
}

export interface AskResponse {
  answer: string;
  sources: AskSource[];
  confidence: number;
  confidence_label: ConfidenceLabel;
  evidence_status: EvidenceStatus;
  follow_up_question: string;
  used_scope: string[];
  answer_mode: AnswerMode;
  trust_mode: boolean;
}

export interface SourceCatalogItem {
  source_file: string;
  chunks: number;
  pages: number;
  kind: string;
  last_added_at: string;
}

export interface SourceCatalogResponse {
  sources: SourceCatalogItem[];
}

export interface FeatureStatus {
  id: string;
  label: string;
  status: "active" | "fallback" | "missing";
  detail: string;
}

export type GraphNodeType = "topic" | "person" | "project" | "doc" | "other";

export interface GraphNode {
  id: string;
  label: string;
  type: GraphNodeType;
  mentions: number;
  degree: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store"
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(formatErrorMessage(text, `Request failed: ${res.status}`));
  }
  return (await res.json()) as T;
}

export async function healthCheck() {
  return req<{ ok: boolean; configured: boolean; unlocked: boolean }>("/health");
}

export async function getSecurityStatus(): Promise<SecurityStatus> {
  return req<SecurityStatus>("/security/status");
}

export async function setupSecurity(passphrase: string): Promise<SecurityStatus> {
  return req<SecurityStatus>("/security/setup", {
    method: "POST",
    body: JSON.stringify({ passphrase })
  });
}

export async function unlockSecurity(passphrase: string): Promise<SecurityStatus> {
  return req<SecurityStatus>("/security/unlock", {
    method: "POST",
    body: JSON.stringify({ passphrase })
  });
}

export async function lockSecurity(): Promise<SecurityStatus> {
  return req<SecurityStatus>("/security/lock", { method: "POST" });
}

export async function ingestFiles(files: File[]): Promise<IngestResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await fetch(`${API_BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(formatErrorMessage(text, `Ingest failed: ${res.status}`));
  }
  return (await res.json()) as IngestResponse;
}

export async function ingestDemoData(): Promise<IngestResponse> {
  return req<IngestResponse>("/ingest_demo", { method: "POST" });
}

export async function reindexKnowledgeBase(): Promise<IngestResponse> {
  return req<IngestResponse>("/reindex", { method: "POST" });
}

export async function getStatus(jobId: string): Promise<JobStatus> {
  return req<JobStatus>(`/status?job_id=${encodeURIComponent(jobId)}`);
}

export async function getStats(): Promise<StatsResponse> {
  return req<StatsResponse>("/stats");
}

export async function getInsights(): Promise<InsightsResponse> {
  return req<InsightsResponse>("/insights");
}

export async function getCatalog(): Promise<SourceCatalogResponse> {
  return req<SourceCatalogResponse>("/catalog");
}

export async function semanticSearch(
  query: string,
  options?: {
    topK?: number;
    sourceFiles?: string[];
  }
): Promise<SearchResponse> {
  return req<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({
      query,
      top_k: options?.topK ?? 5,
      source_files: options?.sourceFiles ?? []
    })
  });
}

export async function askQuestion(
  question: string,
  options?: {
    topK?: number;
    sourceFiles?: string[];
    mode?: AnswerMode;
    trustMode?: boolean;
  }
): Promise<AskResponse> {
  return req<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      top_k: options?.topK ?? 5,
      source_files: options?.sourceFiles ?? [],
      mode: options?.mode ?? "answer",
      trust_mode: options?.trustMode ?? true
    })
  });
}

export async function getGraph(): Promise<GraphResponse> {
  return req<GraphResponse>("/graph");
}
