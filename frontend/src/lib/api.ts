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
  reranker_mode: string;
  reranker_model: string;
  graph_mode: string;
  pdf_backend: string;
  llm_mode: string;
  llm_model: string;
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

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  created_at: string;
  sources?: AskSource[];
  confidence?: number;
  confidence_label?: ConfidenceLabel;
  evidence_status?: EvidenceStatus;
  follow_up_question?: string;
  answer_mode?: AnswerMode;
  used_scope?: string[];
  trust_mode?: boolean;
}

export interface ConversationSummary {
  session_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  last_message_preview: string;
}

export interface ConversationDetail {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
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
  session_id?: string;
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

export interface EvaluationStack {
  llm_mode: string;
  llm_model: string;
  embedding_mode: string;
  embedding_model: string;
  reranker_mode: string;
  reranker_model: string;
}

export interface EvaluationInventory {
  llm_files: string[];
  embedding_folders: string[];
  reranker_folders: string[];
}

export interface EvaluationCase {
  query: string;
  source_file: string;
  expected_chunk_id: string;
  top_hit_chunk_id: string;
  top_hit_source_file: string;
  rank: number | null;
  hit_in_top_1: boolean;
  hit_in_top_3: boolean;
  hit_in_top_5: boolean;
}

export interface EvaluationResponse {
  total_cases: number;
  retrieval_top1: number;
  retrieval_top3: number;
  retrieval_top5: number;
  mean_reciprocal_rank: number;
  avg_query_terms: number;
  stack: EvaluationStack;
  available_models: EvaluationInventory;
  cases: EvaluationCase[];
}

export interface ModelOption {
  id: string;
  label: string;
  detail: string;
}

export interface ModelGroupState {
  selected: string;
  active_mode: string;
  active_model: string;
  requires_reindex?: boolean;
  options: ModelOption[];
}

export interface ModelValidationState {
  ok: boolean;
  detail: string;
  selected: string;
  active_mode: string;
  active_model: string;
}

export interface ModelRoots {
  llm: string;
  embedding: string;
  reranker: string;
}

export interface ModelManagerResponse {
  indexed_chunks: number;
  reindex_recommended: boolean;
  index_embedding_model: string;
  index_embedding_signature: string;
  model_roots: ModelRoots;
  llm: ModelGroupState;
  embedding: ModelGroupState;
  reranker: ModelGroupState;
  validation: {
    llm: ModelValidationState;
    embedding: ModelValidationState;
    reranker: ModelValidationState;
  };
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
  files.forEach((file) => form.append("files", file));
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

export async function getConversations(): Promise<{ conversations: ConversationSummary[] }> {
  return req<{ conversations: ConversationSummary[] }>("/conversations");
}

export async function createConversation(): Promise<ConversationDetail> {
  return req<ConversationDetail>("/conversations", { method: "POST" });
}

export async function getConversation(sessionId: string): Promise<ConversationDetail> {
  return req<ConversationDetail>(`/conversations/${encodeURIComponent(sessionId)}`);
}

export async function deleteConversation(sessionId: string): Promise<{ ok: boolean }> {
  return req<{ ok: boolean }>(`/conversations/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export async function getEvaluation(): Promise<EvaluationResponse> {
  return req<EvaluationResponse>("/evaluate");
}

export async function getModelManager(): Promise<ModelManagerResponse> {
  return req<ModelManagerResponse>("/models");
}

export async function applyModelManagerSettings(payload: {
  llm?: string;
  embedding?: string;
  reranker?: string;
}): Promise<ModelManagerResponse> {
  return req<ModelManagerResponse>("/models/apply", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function validateModelManagerSettings(payload: {
  llm?: string;
  embedding?: string;
  reranker?: string;
}): Promise<ModelManagerResponse> {
  return req<ModelManagerResponse>("/models/validate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
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
    sessionId?: string;
  }
): Promise<AskResponse> {
  return req<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      top_k: options?.topK ?? 5,
      source_files: options?.sourceFiles ?? [],
      mode: options?.mode ?? "answer",
      trust_mode: options?.trustMode ?? true,
      session_id: options?.sessionId
    })
  });
}

export async function getGraph(): Promise<GraphResponse> {
  return req<GraphResponse>("/graph");
}
