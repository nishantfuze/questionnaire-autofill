const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

export interface HealthResponse {
  status: string;
  knowledge_base_entries: number;
}

export interface FillResult {
  question: string;
  answer: string;
  confidence_score: number;
  confidence_level: string;
  evidence: string;
  similarity_score: number;
}

export interface FillResponse {
  total_questions: number;
  results: FillResult[];
  csv_output: string;
  summary: {
    high: number;
    medium: number;
    low: number;
    requires_human_attention: number;
  };
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

export async function fillQuestionnaire(file: File): Promise<FillResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/api/v1/questionnaire/fill-json`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = `Request failed: ${response.status}`;
    try {
      const errorJson = JSON.parse(errorText);
      errorMessage = errorJson.detail || errorMessage;
    } catch {
      if (errorText) errorMessage = errorText;
    }
    throw new Error(errorMessage);
  }

  return response.json();
}
