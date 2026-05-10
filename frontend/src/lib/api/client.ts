import type {
  AvailableYearsResponse,
  CompareYearsRequest,
  CompareYearsResponse,
  DeleteResponse,
  EmployerCreate,
  EmployerResponse,
  FilingStatus,
  NonTaxableIncomeCreate,
  NonTaxableIncomeResponse,
  PaycheckCreate,
  PaycheckResponse,
  ProjectYearRequest,
  ProjectYearResponse,
  Retirement1099RCreate,
  Retirement1099RResponse,
  TaxCalculationRequest,
  TaxCalculationResponse,
  TaxReconciliationResponse,
  W4OptimizeRequest,
  W4OptimizeResponse,
  WithholdingCalcRequest,
  WithholdingCalcResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const buildUrl = (path: string, queryParams?: Record<string, string | number | undefined>) => {
  const origin = typeof window === "undefined" ? "http://127.0.0.1:8000" : window.location.origin;
  const url = new URL(path, API_BASE_URL || origin);

  if (queryParams) {
    for (const [key, value] of Object.entries(queryParams)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  return url;
};

const request = async <T>(path: string, queryParams?: Record<string, string | number | undefined>): Promise<T> => {
  const response = await fetch(buildUrl(path, queryParams));

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep generic detail if response is not JSON.
    }

    throw new Error(detail);
  }

  return (await response.json()) as T;
};

const post = async <T>(path: string, body: unknown): Promise<T> => {
  const origin = typeof window === "undefined" ? "http://127.0.0.1:8000" : window.location.origin;
  const url = new URL(path, API_BASE_URL || origin);

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep generic detail if response is not JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

const del = async <T>(path: string): Promise<T> => {
  const origin = typeof window === "undefined" ? "http://127.0.0.1:8000" : window.location.origin;
  const url = new URL(path, API_BASE_URL || origin);

  const response = await fetch(url, { method: "DELETE" });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep generic detail if response is not JSON.
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

export const apiClient = {
  // Tax data
  getAvailableYears: () => request<AvailableYearsResponse>("/taxes/tax-data/available-years"),

  // Tax calculation
  calculateTaxes: (data: TaxCalculationRequest) => post<TaxCalculationResponse>("/taxes/calculate", data),
  calculateFromDb: (
    year: number,
    params: {
      filing_status: FilingStatus;
      num_children: number;
      use_standard_deduction: boolean;
      itemized_deduction_amount: number;
    },
  ) =>
    request<TaxReconciliationResponse>(`/taxes/calculate-from-db/${year}`, {
      filing_status: params.filing_status,
      num_children: params.num_children,
      use_standard_deduction: params.use_standard_deduction ? "true" : "false",
      itemized_deduction_amount: params.itemized_deduction_amount,
    }),

  // Employers
  listEmployers: () => request<EmployerResponse[]>("/income/employers"),
  createEmployer: (data: EmployerCreate) => post<EmployerResponse>("/income/employers", data),

  // Paychecks
  listPaychecks: (year?: number) => request<PaycheckResponse[]>("/income/paychecks", { year }),
  createPaycheck: (data: PaycheckCreate) => post<PaycheckResponse>("/income/paychecks", data),
  deletePaycheck: (id: number) => del<DeleteResponse>(`/income/paychecks/${id}`),

  // 1099-R Pensions
  listPensions: (year?: number) => request<Retirement1099RResponse[]>("/income/1099r", { year }),
  createPension: (data: Retirement1099RCreate) => post<Retirement1099RResponse>("/income/1099r", data),
  deletePension: (id: number) => del<DeleteResponse>(`/income/1099r/${id}`),

  // Non-taxable income
  listNonTaxableIncome: (year?: number) => request<NonTaxableIncomeResponse[]>("/income/non-taxable", { year }),
  createNonTaxableIncome: (data: NonTaxableIncomeCreate) => post<NonTaxableIncomeResponse>("/income/non-taxable", data),
  deleteNonTaxableIncome: (id: number) => del<DeleteResponse>(`/income/non-taxable/${id}`),

  // W-4
  optimizeW4: (data: W4OptimizeRequest) => post<W4OptimizeResponse>("/w4/optimize", data),
  calculateWithholding: (data: WithholdingCalcRequest) =>
    post<WithholdingCalcResponse>("/w4/calculate-withholding", data),

  // Projections
  projectYear: (data: ProjectYearRequest) => post<ProjectYearResponse>("/projections/project-year", data),
  compareYears: (data: CompareYearsRequest) => post<CompareYearsResponse>("/projections/compare-years", data),
};
