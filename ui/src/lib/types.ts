export interface Collection {
	id: number;
	name: string;
	description_style: string | null;
	controlled_vocabulary: string | null;
	known_locations: string | null;
	known_date_range: string | null;
	known_people_orgs: string | null;
	terms_to_avoid: string | null;
	institutional_rules: string | null;
	rights_sensitivity_notes: string | null;
	created_at: string;
}

export interface ImageEntry {
	id: number;
	filename: string;
	filepath: string;
	collection_id: number;
	ingested_at: string;
	status: string;
	draft_generated: boolean;
}

export interface MetadataRecord {
	id: number;
	image_id: number;
	title: string | null;
	description: string | null;
	visible_text: string | null;
	subjects: string[];
	people: string[];
	places: string[];
	dates: string | null;
	objects: string[];
	uncertainty_notes: string | null;
	reviewer_notes: string | null;
	review_status: string;
	draft_generated: boolean;
	last_revised_at: string | null;
	approved_at: string | null;
}

export interface RevisionEntry {
	id: number;
	revision_type: string;
	revised_by: string;
	revised_at: string;
	feedback_given: string | null;
	snapshot: string;
}

export interface StatusCounts {
	needs_review?: number;
	in_progress?: number;
	revised?: number;
	approved?: number;
	flagged?: number;
}
