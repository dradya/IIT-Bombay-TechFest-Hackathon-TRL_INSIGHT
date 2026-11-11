/* TypeScript interfaces mirroring the TRL INSIGHT API JSON contract.
   All field names are snake_case exactly as returned by the backend.
   Additive 2.0 fields are optional so pre-2.0 assessments still type-check. */

// ---------------------------------------------------------------------------
// Health / system
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  model_available: boolean;
  model_mode: string;
  database: string;
  time: string;
}

export interface CapabilityEntry {
  configured?: string;
  active?: string;
  available?: boolean;
  [key: string]: unknown;
}

export interface CapabilitiesResponse {
  parser: {
    configured: string;
    docling_available: boolean;
    active: string;
    native_fallback: string;
    note: string;
  };
  embeddings: {
    configured: string;
    active: string;
    model: string;
    available: boolean;
    fallback_reason: string;
    cache: string;
    sentence_transformers_installed: boolean;
    flag_embedding_installed: boolean;
    note: string;
  };
  shap: {
    enabled: boolean;
    installed: boolean;
    fallback: string;
    note: string;
  };
  haystack: {
    installed: boolean;
    integrated: boolean;
    reason: string;
  };
  osstrl: {
    installed: boolean;
    integrated: boolean;
    license: string;
    reason: string;
  };
  semantic_retrieval: {
    enabled: boolean;
    backend: string;
  };
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------
export interface PageText {
  page: number;
  text: string;
  chars: number;
}

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  size_bytes: number;
  page_count: number;
  char_count: number;
  uploaded_at: string;
  preview_text: string;
  preview_pages: PageText[];
  headings: string[];
  has_tables: boolean;
  ocr_used: boolean;
  warnings: string[];
  extraction_method: string;
  metadata: Record<string, unknown>;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  size_bytes: number;
  page_count: number;
  char_count: number;
  uploaded_at: string;
}

export interface DocumentSummary {
  document_id: string | null;
  filename: string;
  page_count: number;
  char_count: number;
  uploaded_at: string | null;
  extraction_method: string;
  evidence_count: number;
  confirmed: number;
  proposed: number;
  contradicted: number;
  unclear: number;
  duplicates: number;
  outdated: number;
}

// ---------------------------------------------------------------------------
// Evidence
// ---------------------------------------------------------------------------
export type EvidenceStatus = "confirmed" | "proposed" | "contradicted" | "unclear";
export type MilestoneStatusValue = "confirmed" | "not_found" | "contradicted" | "unclear";
export type Stance = "supporting" | "contradicting" | "insufficient";
export type EvidenceType = "document" | "self_reported";

export interface EvidenceItem {
  id: string;
  statement: string;
  category: string;
  category_label: string;
  status: EvidenceStatus;
  stance: Stance;
  source_document: string;
  page_number: number | null;
  location: string;
  section: string;
  milestone: string | null;
  milestone_label: string | null;
  supports_milestone: boolean;
  relevance: number;
  is_proposed: boolean;
  future_tense: boolean;
  negated: boolean;
  // Additive 2.0 provenance / graph fields
  document_id?: string | null;
  evidence_type?: EvidenceType;
  duplicate_group?: string | null;
  duplicate_of?: string | null;
  duplicate_count?: number;
  superseded_by?: string | null;
  outdated?: boolean;
  semantic_similarity?: number | null;
  semantic_milestone?: string | null;
}

export interface EvidenceCategoryCount {
  category: string;
  label: string;
  count: number;
  confirmed: number;
  proposed: number;
  contradicted: number;
  unclear: number;
}

export interface EvidenceSummary {
  total: number;
  confirmed: number;
  proposed: number;
  contradicted: number;
  unclear: number;
  by_category: EvidenceCategoryCount[];
  coverage: number;
  // Additive 2.0 fields
  raw_total?: number;
  duplicates?: number;
  outdated?: number;
  self_reported?: number;
}

// ---------------------------------------------------------------------------
// Milestones / prediction / verification / gap analysis
// ---------------------------------------------------------------------------
export interface MilestoneStatusModel {
  id: string;
  trl: number;
  label: string;
  status: MilestoneStatusValue;
  evidence_count: number;
  supporting: number;
  contradicting: number;
  proposed: number;
  summary: string;
  evidence_ids: string[];
}

export interface LevelProbability {
  level: number;
  probability: number;
}

export interface AlternativeLevel {
  level: number;
  probability: number;
  reason: string;
}

export interface Prediction {
  predicted_trl: number;
  level_name: string;
  level_category: string;
  level_description: string;
  confidence: number;
  low_confidence: boolean;
  evidence_coverage: number;
  probabilities: LevelProbability[];
  alternatives: AlternativeLevel[];
  rule_level: number | null;
  ml_level: number | null;
  model_mode: "hybrid" | "rule_only";
  warnings: string[];
  method: string;
  model_probability?: number | null;
}

export interface VerificationResult {
  predicted_trl: number;
  evidence_backing: EvidenceItem[];
  contradictions: EvidenceItem[];
  proposed_mistaken_for_done: EvidenceItem[];
  unsupported_high_level_claim: boolean;
  concerns: string[];
  summary: string;
}

export interface Recommendation {
  id: string;
  title: string;
  addresses: string[];
  address_labels: string[];
  address_statuses: string[];
  actions: string[];
  validation_experiments: string[];
  documentation: string[];
  priority: "high" | "medium" | "low";
}

export interface GapAnalysis {
  current_trl: number;
  current_name: string;
  next_trl: number | null;
  next_name: string | null;
  completed_milestones: MilestoneStatusModel[];
  missing_milestones: MilestoneStatusModel[];
  unclear_milestones: MilestoneStatusModel[];
  contradicted_milestones: MilestoneStatusModel[];
  recommendations: Recommendation[];
  documentation_requirements: string[];
  summary: string;
}

export interface ModelInfo {
  available: boolean;
  name: string;
  version: string;
  mode: "hybrid" | "rule_only";
  dataset_type: string;
  trained_at: string | null;
}

export interface ProcessingInfo {
  extraction_method: string;
  pages: number;
  sentences: number;
  evidence_items: number;
  ocr_used: boolean;
  duration_ms: number;
  documents: number;
  duplicates: number;
  outdated: number;
}

export interface AssessmentMetadata {
  technology_name: string;
  domain: string;
  organization: string;
  description: string;
  filename: string;
}

// ---------------------------------------------------------------------------
// 2.0 intelligence blocks (mirrors backend/app/schemas/intelligence.py)
// ---------------------------------------------------------------------------
export interface RetrievalMatch {
  evidence_id: string;
  statement: string;
  source_document: string;
  page_number: number | null;
  location: string;
  status: string;
  similarity: number;
}

export interface MilestoneRetrieval {
  milestone: string;
  matches: RetrievalMatch[];
}

export interface RetrievalInfo {
  enabled: boolean;
  method: string;
  model: string;
  backend: string;
  cached: boolean;
  fallback_reason: string;
  by_milestone: MilestoneRetrieval[];
  note: string;
}

export type ContradictionType =
  | "explicit_contradiction"
  | "cross_document_conflict"
  | "category_conflict"
  | "outdated_conflict";

export interface ContradictionSource {
  evidence_id: string;
  statement: string;
  source_document: string;
  document_id: string | null;
  page_number: number | null;
  location: string;
  status: string;
  uploaded_at: string | null;
  outdated: boolean;
}

export interface ContradictionItem {
  id: string;
  type: ContradictionType;
  severity: "high" | "medium" | "low";
  milestone: string | null;
  milestone_label: string | null;
  category: string | null;
  category_label: string | null;
  explanation: string;
  sources: ContradictionSource[];
  human_verification: string[];
  suggested_action: string;
}

export interface ContradictionReport {
  total: number;
  by_type: Record<string, number>;
  items: ContradictionItem[];
  summary: string;
}

export interface Uncertainty {
  model_probability: number | null;
  confidence: number;
  coverage: number;
  completeness: number;
  reliability: number;
  overall: number;
  band: "low" | "medium" | "high";
  calibrated: boolean;
  calibration_source: string | null;
  calibration_note: string;
  components: Record<string, number | null>;
  explanation: string;
}

export type GraphNodeType =
  | "technology"
  | "document"
  | "milestone"
  | "category"
  | "evidence"
  | "contradiction";

export type GraphEdgeType =
  | "contains"
  | "supports"
  | "contradicts"
  | "duplicate_of"
  | "derived_from"
  | "relates_to";

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  status: string | null;
  document_id: string | null;
  page_number: number | null;
  weight: number;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  label: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
  truncated: boolean;
  note: string;
}

export interface RoadmapAction {
  id: string;
  title: string;
  description: string;
  milestone: string | null;
  milestone_label: string | null;
  status: string;
  priority: "high" | "medium" | "low";
  actions: string[];
  validation_experiments: string[];
  documentation: string[];
  success_criteria: string[];
}

export interface RoadmapPhase {
  id: string;
  title: string;
  horizon: "now" | "next" | "later";
  target_trl: number | null;
  summary: string;
  items: RoadmapAction[];
}

export interface TechnologyRoadmap {
  current_trl: number;
  current_name: string;
  target_trl: number | null;
  target_name: string | null;
  phases: RoadmapPhase[];
  note: string;
}

export interface QuestionItem {
  id: string;
  milestone: string;
  milestone_label: string;
  trl: number;
  status: string;
  question: string;
  why_it_matters: string;
  expected_document: string;
  options: string[];
}

export interface Questionnaire {
  assessment_id: string;
  generated_at: string;
  total: number;
  items: QuestionItem[];
  note: string;
}

export type ExpertAnswerStatus = "completed" | "planned" | "not_applicable" | "unknown";

export interface ExpertAnswer {
  milestone_id: string;
  status: ExpertAnswerStatus;
  evidence_note: string;
  source_reference: string;
}

export interface ReassessRequest {
  answers: ExpertAnswer[];
  reviewer_name: string;
  reason: string;
}

export interface ShapFeature {
  feature: string;
  label: string;
  value: number;
  contribution: number;
  direction: "supports" | "opposes" | "neutral";
  kind: "text" | "evidence";
}

export interface ModelExplanation {
  available: boolean;
  method: string;
  target_trl: number | null;
  baseline: number | null;
  prediction_probability: number | null;
  features: ShapFeature[];
  note: string;
  warning: string;
}

export type ReviewDecision = "accept" | "override" | "needs_more_evidence";

export interface ReviewCreate {
  reviewer_name: string;
  decision: ReviewDecision;
  reviewed_trl?: number | null;
  notes: string;
  evidence_ids: string[];
}

export interface ReviewModel {
  id: string;
  assessment_id: string;
  reviewer_name: string;
  decision: ReviewDecision;
  reviewed_trl: number | null;
  ai_trl: number | null;
  notes: string;
  evidence_ids: string[];
  created_at: string;
}

export interface ReviewListResponse {
  assessment_id: string;
  items: ReviewModel[];
  total: number;
  ai_prediction: {
    predicted_trl?: number | null;
    confidence?: number | null;
    evidence_coverage?: number | null;
    model_mode?: string;
    created_at?: string;
    immutable?: boolean;
  };
  latest_decision: string | null;
  review_status: string;
}

export interface TimelineEvent {
  id: string;
  kind: "created" | "reassessment" | "review" | "analysis";
  title: string;
  description: string;
  at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

export interface AssessmentTimeline {
  assessment_id: string;
  events: TimelineEvent[];
}

export interface CompareItem {
  id: string;
  technology_name: string;
  predicted_trl: number | null;
  confidence: number | null;
  evidence_coverage: number | null;
  uncertainty_overall: number | null;
  documents: DocumentSummary[];
  milestones: MilestoneStatusModel[];
  evidence_total: number;
  contradictions_total: number;
  created_at: string;
}

export interface CompareResponse {
  items: CompareItem[];
  note: string;
}

export interface AssessmentResult {
  id: string;
  document_id: string | null;
  created_at: string;
  framework_version?: string;
  metadata: AssessmentMetadata;
  prediction: Prediction;
  evidence: EvidenceItem[];
  evidence_summary: EvidenceSummary;
  milestones: MilestoneStatusModel[];
  verification: VerificationResult | null;
  gap_analysis: GapAnalysis | null;
  model: ModelInfo;
  processing: ProcessingInfo;
  // Additive 2.0 blocks (absent on legacy assessments)
  documents?: DocumentSummary[];
  retrieval?: RetrievalInfo | null;
  contradictions?: ContradictionReport | null;
  graph?: KnowledgeGraph | null;
  uncertainty?: Uncertainty | null;
  roadmap?: TechnologyRoadmap | null;
  questionnaire?: Questionnaire | null;
  model_explanation?: ModelExplanation | null;
  parent_assessment_id?: string | null;
  reassessment_reason?: string | null;
}

// ---------------------------------------------------------------------------
// List / overview
// ---------------------------------------------------------------------------
export interface AssessmentSummary {
  id: string;
  document_id: string | null;
  technology_name: string;
  domain: string;
  organization: string;
  filename: string;
  predicted_trl: number | null;
  level_name: string;
  confidence: number | null;
  low_confidence: boolean;
  evidence_coverage: number | null;
  model_mode: string;
  created_at: string;
  document_count?: number;
  uncertainty_overall?: number | null;
  contradictions_total?: number;
  review_status?: string;
  latest_review_decision?: string | null;
}

export interface AssessmentListResponse {
  items: AssessmentSummary[];
  total: number;
}

export interface TrlCount {
  trl: number;
  count: number;
}

export interface ConfidenceBuckets {
  high: number;
  medium: number;
  low: number;
  average: number | null;
}

export interface CoverageBuckets {
  high: number;
  medium: number;
  low: number;
  average: number | null;
}

export interface DomainCount {
  domain: string;
  count: number;
}

export interface ReviewSummary {
  unreviewed: number;
  accepted: number;
  overridden: number;
  more_evidence_requested: number;
  awaiting_review: number;
}

export interface ActivityItem {
  id: string;
  technology_name: string;
  predicted_trl: number | null;
  confidence: number | null;
  created_at: string;
  kind: string;
}

export interface OverviewResponse {
  has_data: boolean;
  total_assessments: number;
  average_trl: number | null;
  average_confidence: number | null;
  distribution: TrlCount[];
  confidence: ConfidenceBuckets;
  recent: AssessmentSummary[];
  activity: ActivityItem[];
  domains: string[];
  coverage?: CoverageBuckets;
  domain_distribution?: DomainCount[];
  reviews?: ReviewSummary;
  low_confidence?: number;
}

// ---------------------------------------------------------------------------
// TRL reference
// ---------------------------------------------------------------------------
export interface TrlLevel {
  level: number;
  name: string;
  category: string;
  description: string;
  examples: string[];
  requirements: string[];
  progression_criteria: string[];
}

export interface TrlMilestone {
  id: string;
  trl: number;
  label: string;
  description: string;
  completion_required: boolean;
  defining_indicators: string[];
}

export interface EvidenceCategory {
  id: string;
  label: string;
  description: string;
  primary_milestone: string;
  secondary_milestones: string[];
  keywords: string[];
}

export interface TRLReferenceResponse {
  version: string;
  meta: Record<string, unknown>;
  levels: TrlLevel[];
  milestones: TrlMilestone[];
  evidence_categories: EvidenceCategory[];
  evidence_statuses: string[];
  assessment_rules: Record<string, number | string | boolean>;
}

// ---------------------------------------------------------------------------
// Model performance
// ---------------------------------------------------------------------------
export interface ClassMetric {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface ConfusionMatrixData {
  labels: number[];
  matrix: number[][];
}

export interface ClassificationReportRow {
  precision: number;
  recall: number;
  f1: number;
  support: number;
  accuracy?: number;
}

export interface ModelPerformanceResponse {
  available: boolean;
  mode: string;
  note: string;
  model_name: string | null;
  model_version: string | null;
  trained_at: string | null;
  dataset_type: string | null;
  dataset_source: string | null;
  n_train: number | null;
  n_test: number | null;
  class_distribution: Record<string, number>;
  metrics: Record<string, number>;
  per_class: Record<string, ClassMetric>;
  confusion_matrix: ConfusionMatrixData | null;
  /* Mixed record: class labels map to rows, "accuracy" maps to a number. */
  classification_report: Record<string, ClassificationReportRow | number> | null;
  calibration?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Analyze request
// ---------------------------------------------------------------------------
export interface AnalyzeRequest {
  document_id?: string;
  document_ids?: string[];
  technology_name?: string;
  domain?: string;
  organization?: string;
  description?: string;
}
