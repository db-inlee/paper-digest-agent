export interface Evidence {
	page: number | null;
	section: string | null;
	quote: string | null;
	type: string;
}

// --- Extraction ---

export interface ProblemDefinition {
	statement: string;
	baseline_methods: string[];
	structural_limitation: string;
	evidence: Evidence[];
}

export interface Baseline {
	name: string;
	description: string;
	limitation: string;
	evidence: Evidence[];
}

export interface MethodComponent {
	name: string;
	description: string;
	inputs: string[];
	outputs: string[];
	implementation_hint: string | null;
	evidence: Evidence[];
}

export interface Benchmark {
	dataset: string;
	metrics: string[];
	baseline_results: Record<string, string>;
	proposed_results: Record<string, string>;
	evidence: Evidence[];
}

export interface Claim {
	claim_id: string;
	text: string;
	claim_type: string;
	confidence: number;
	evidence: Evidence[];
}

export interface Extraction {
	arxiv_id: string;
	title: string;
	problem_definition: ProblemDefinition;
	baselines: Baseline[];
	method_components: MethodComponent[];
	benchmark: Benchmark;
	claims: Claim[];
	extraction_mode: string;
}

// --- Delta ---

export interface CoreDelta {
	axis: string;
	old_approach: string;
	new_approach: string;
	why_better: string;
	evidence: Evidence;
}

export interface Tradeoff {
	aspect: string;
	benefit: string;
	cost: string;
	when_acceptable: string;
	evidence?: Evidence;
}

export interface Delta {
	arxiv_id: string;
	one_line_takeaway: string;
	core_deltas: CoreDelta[];
	tradeoffs: Tradeoff[];
	when_to_use: string;
	when_not_to_use: string;
}

// --- Scoring ---

export interface Scoring {
	arxiv_id: string;
	practicality: number;
	codeability: number;
	signal: number;
	recommendation: string;
	reasoning: string;
	key_strength: string;
	main_concern: string;
}

// --- Verification ---

export interface VerificationResult {
	claim_id: string;
	claim_text: string;
	status: 'verified' | 'unverified' | 'contradicted';
	confidence: number;
	evidence_found: string;
	notes: string;
	correction_hint: string | null;
}

export interface Verification {
	arxiv_id: string;
	total_claims: number;
	verified_count: number;
	unverified_count: number;
	contradicted_count: number;
	overall_reliability: 'high' | 'medium' | 'low';
	results: VerificationResult[];
	summary: string;
	corrections_needed: string[];
}

// --- Combined ---

export interface PaperDetail {
	arxiv_id: string;
	extraction: Extraction | null;
	delta: Delta | null;
	scoring: Scoring | null;
	verification: Verification | null;
}
