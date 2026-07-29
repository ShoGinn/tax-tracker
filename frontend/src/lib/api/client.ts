import type {
  AppConfigUpdate,
  AvailableYearsResponse,
  CompareYearsRequest,
  CompareYearsResponse,
  CsvImportType,
  DashboardProjectionResponse,
  EmployerCreate,
  EmployerUpdate,
  FilingStatus,
  MidYearDBW4OptimizeRequest,
  MidYearPeriodSuggestionRequest,
  MidYearPeriodSuggestionResponse,
  MidYearW4OptimizeResponse,
  NonTaxableIncomeCreate,
  NonTaxableIncomeUpdate,
  PaycheckCreate,
  PaycheckUpdate,
  ProjectYearRequest,
  ProjectYearResponse,
  Retirement1099RCreate,
  Retirement1099RUpdate,
  TaxCalculationRequest,
  TaxCalculationResponse,
  TaxReconciliationResponse,
  W4OptimizeRequest,
  W4OptimizeResponse,
  WithholdingCalcRequest,
  WithholdingCalcResponse,
} from "./types";
import { browserStore } from "../storage/browserStore";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

type QueryValue = string | number | boolean | undefined;

interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown | FormData;
  signal?: AbortSignal;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const buildUrl = (path: string, queryParams?: Record<string, QueryValue>) => {
  const origin = typeof window === "undefined" ? "http://127.0.0.1:8000" : window.location.origin;
  const url = API_BASE_URL
    ? new URL(path.replace(/^\//, ""), `${API_BASE_URL.replace(/\/+$/, "")}/`)
    : new URL(path, origin);

  if (queryParams) {
    for (const [key, value] of Object.entries(queryParams)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  return url;
};

const request = async <T>(path: string, options: ApiRequestOptions = {}): Promise<T> => {
  const isMultipart = options.body instanceof FormData;
  let requestBody: BodyInit | undefined;
  if (options.body instanceof FormData) {
    requestBody = options.body;
  } else if (options.body !== undefined) {
    requestBody = JSON.stringify(options.body);
  }

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? "GET",
    headers:
      options.body !== undefined && !isMultipart
        ? { "Content-Type": "application/json" }
        : undefined,
    body: requestBody,
    signal: options.signal,
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
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
};

const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body, signal });
export const apiClient = {
  // Tax data
  getAvailableYears: () => request<AvailableYearsResponse>("/taxes/tax-data/available-years"),

  // Tax calculation
  calculateTaxes: (data: TaxCalculationRequest) =>
    post<TaxCalculationResponse>("/taxes/calculate", data),
  calculateFromDb: async (
    year: number,
    params: {
      filing_status: FilingStatus;
      num_children: number;
      use_standard_deduction: boolean;
      itemized_deduction_amount: number;
    },
  ) =>
    post<TaxReconciliationResponse>(`/taxes/reconcile-records/${year}`, {
      ...(await browserStore.snapshot(year)),
      options: {
        filing_status: params.filing_status,
        num_children: params.num_children,
        use_standard_deduction: params.use_standard_deduction,
        itemized_deduction_amount: params.itemized_deduction_amount,
      },
    }),

  // Employers
  listEmployers: () => browserStore.listEmployers(),
  createEmployer: (data: EmployerCreate) => browserStore.createEmployer(data),
  updateEmployer: (id: number, data: EmployerUpdate) => browserStore.updateEmployer(id, data),
  deleteEmployer: (id: number) => browserStore.deleteEmployer(id),

  // Paychecks
  listPaychecks: (year?: number) => browserStore.listPaychecks(year),
  createPaycheck: (data: PaycheckCreate) => browserStore.createPaycheck(data),
  updatePaycheck: (id: number, data: PaycheckUpdate) => browserStore.updatePaycheck(id, data),
  deletePaycheck: (id: number) => browserStore.deletePaycheck(id),

  // 1099-R Pensions
  listPensions: (year?: number) => browserStore.listPensions(year),
  createPension: (data: Retirement1099RCreate) => browserStore.createPension(data),
  updatePension: (id: number, data: Retirement1099RUpdate) => browserStore.updatePension(id, data),
  deletePension: (id: number) => browserStore.deletePension(id),

  // Non-taxable income
  listNonTaxableIncome: (year?: number) => browserStore.listNonTaxableIncome(year),
  createNonTaxableIncome: (data: NonTaxableIncomeCreate) =>
    browserStore.createNonTaxableIncome(data),
  updateNonTaxableIncome: (id: number, data: NonTaxableIncomeUpdate) =>
    browserStore.updateNonTaxableIncome(id, data),
  deleteNonTaxableIncome: (id: number) => browserStore.deleteNonTaxableIncome(id),
  importCsv: (type: CsvImportType, file: File, _signal?: AbortSignal) =>
    browserStore.importCsv(type, file),

  // W-4
  optimizeW4: (data: W4OptimizeRequest) => post<W4OptimizeResponse>("/w4/optimize", data),
  suggestMidyearPeriods: async (data: MidYearPeriodSuggestionRequest) =>
    post<MidYearPeriodSuggestionResponse>("/w4/suggest-periods", {
      ...data,
      ...(await browserStore.snapshot(data.tax_year)),
    }),
  optimizeMidyearW4: async (data: MidYearDBW4OptimizeRequest) =>
    post<MidYearW4OptimizeResponse>("/w4/optimize-midyear", {
      ...data,
      ...(await browserStore.snapshot(data.tax_year)),
    }),
  calculateWithholding: (data: WithholdingCalcRequest) =>
    post<WithholdingCalcResponse>("/w4/calculate-withholding", data),

  // Projections
  projectYear: (data: ProjectYearRequest) =>
    post<ProjectYearResponse>("/projections/project-year", data),
  compareYears: (data: CompareYearsRequest) =>
    post<CompareYearsResponse>("/projections/compare-years", data),
  getDashboardProjection: async (year: number) =>
    post<DashboardProjectionResponse>(
      `/projections/dashboard/${year}`,
      await browserStore.snapshot(year),
    ),

  // App config
  getConfig: () => browserStore.getConfig(),
  updateConfig: (data: AppConfigUpdate) => browserStore.updateConfig(data),
};
