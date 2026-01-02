/**
 * API client for the Finalyzer backend
 */

const API_BASE = "/api";

export interface Transaction {
  id: string;
  source: string;
  source_file_hash: string;
  transaction_hash: string;
  date: string;
  description: string;
  amount: number;
  category: string | null;
  raw_category: string | null;
  tags: string[];
}

export interface UploadResponse {
  filename: string;
  source: string;
  transactions_added: number;
  transactions_skipped: number;
  message: string;
}

export interface UploadedFile {
  id: string;
  filename: string;
  file_hash: string;
  source: string;
  transaction_count: number;
  uploaded_at: string;
}

export interface QueryResponse {
  summary: string;
  transactions: Transaction[];
  total_amount: number | null;
}

export interface HealthResponse {
  status: string;
  transaction_count: number;
}

export interface SpendingSummary {
  by_category: Record<string, number>;
  total: number;
}

export interface Settings {
  llm_provider: string;
  ollama_host: string;
  has_openai_key: boolean;
}

export interface SettingsUpdate {
  llm_provider?: string;
  ollama_host?: string;
  openai_api_key?: string;
}

export interface ProcessingJob {
  file_hash: string;
  filename: string;
  total: number;
  processed: number;
  status: "processing" | "complete" | "error";
  elapsed_seconds: number;
  error: string | null;
}

export interface ProcessingStatus {
  jobs: ProcessingJob[];
  has_active: boolean;
}

// Dashboard types
export interface DashboardOverview {
  total_transactions: number;
  total_spending: number;
  total_income: number;
  date_range: { start: string; end: string } | null;
  categories_count: number;
  sources_count: number;
}

export interface CategorySpending {
  data: { category: string; amount: number }[];
  total: number;
}

export interface MonthlySpending {
  data: {
    month: string;
    spending: number;
    income: number;
    net: number;
    count: number;
  }[];
}

export interface MonthlyByCategory {
  data: Record<string, number | string>[];
  categories: string[];
}

export interface YearComparison {
  data: {
    year: number;
    spending: number;
    income: number;
    count: number;
    yoy_change?: number;
  }[];
}

export interface TopMerchant {
  merchant: string;
  amount: number;
  count: number;
}

export interface SourceSpending {
  data: { source: string; amount: number; count: number }[];
}

export interface DailySpending {
  data: { date: string; amount: number }[];
}

class ApiClient {
  private async fetch<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  async healthCheck(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>("/health");
  }

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }

    return response.json();
  }

  async getTransactions(params?: {
    start_date?: string;
    end_date?: string;
    category?: string;
    source?: string;
    limit?: number;
  }): Promise<Transaction[]> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set("start_date", params.start_date);
    if (params?.end_date) searchParams.set("end_date", params.end_date);
    if (params?.category) searchParams.set("category", params.category);
    if (params?.source) searchParams.set("source", params.source);
    if (params?.limit) searchParams.set("limit", params.limit.toString());

    const query = searchParams.toString();
    return this.fetch<Transaction[]>(`/transactions${query ? `?${query}` : ""}`);
  }

  async query(queryText: string): Promise<QueryResponse> {
    return this.fetch<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({ query: queryText }),
    });
  }

  async getSummary(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<SpendingSummary> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set("start_date", params.start_date);
    if (params?.end_date) searchParams.set("end_date", params.end_date);

    const query = searchParams.toString();
    return this.fetch<SpendingSummary>(`/summary${query ? `?${query}` : ""}`);
  }

  async getUploadedFiles(): Promise<{ files: UploadedFile[] }> {
    return this.fetch<{ files: UploadedFile[] }>("/files");
  }

  async getSettings(): Promise<Settings> {
    return this.fetch<Settings>("/settings");
  }

  async updateSettings(settings: SettingsUpdate): Promise<void> {
    await this.fetch("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  }

  async getProcessingStatus(): Promise<ProcessingStatus> {
    return this.fetch<ProcessingStatus>("/processing-status");
  }

  // Dashboard endpoints
  async getDashboardOverview(year?: number): Promise<DashboardOverview> {
    const query = year ? `?year=${year}` : "";
    return this.fetch<DashboardOverview>(`/dashboard/overview${query}`);
  }

  async getSpendingByCategory(year?: number): Promise<CategorySpending> {
    const query = year ? `?year=${year}` : "";
    return this.fetch<CategorySpending>(`/dashboard/spending-by-category${query}`);
  }

  async getMonthlySpending(year?: number): Promise<MonthlySpending> {
    const query = year ? `?year=${year}` : "";
    return this.fetch<MonthlySpending>(`/dashboard/monthly-spending${query}`);
  }

  async getMonthlyByCategory(year?: number): Promise<MonthlyByCategory> {
    const query = year ? `?year=${year}` : "";
    return this.fetch<MonthlyByCategory>(`/dashboard/monthly-by-category${query}`);
  }

  async getYearComparison(): Promise<YearComparison> {
    return this.fetch<YearComparison>("/dashboard/year-comparison");
  }

  async getTopMerchants(params?: {
    limit?: number;
    year?: number;
  }): Promise<{ data: TopMerchant[] }> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", params.limit.toString());
    if (params?.year) searchParams.set("year", params.year.toString());
    const query = searchParams.toString();
    return this.fetch<{ data: TopMerchant[] }>(`/dashboard/top-merchants${query ? `?${query}` : ""}`);
  }

  async getSpendingBySource(year?: number): Promise<SourceSpending> {
    const query = year ? `?year=${year}` : "";
    return this.fetch<SourceSpending>(`/dashboard/spending-by-source${query}`);
  }

  async getDailySpending(params?: { days?: number; year?: number }): Promise<DailySpending> {
    const searchParams = new URLSearchParams();
    if (params?.days) searchParams.set("days", params.days.toString());
    if (params?.year) searchParams.set("year", params.year.toString());
    const query = searchParams.toString();
    return this.fetch<DailySpending>(`/dashboard/daily-spending${query ? `?${query}` : ""}`);
  }
}

export const api = new ApiClient();

