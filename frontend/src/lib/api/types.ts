export type DecimalString = string;

export interface EmployerResponse {
  id: number;
  name: string;
  ein: string | null;
  start_date: string;
  end_date: string | null;
  notes: string | null;
}

export interface EmployerCreate {
  name: string;
  ein?: string | null;
  start_date: string;
  end_date?: string | null;
  notes?: string | null;
}

export interface PaycheckResponse {
  id: number;
  employer_id: number;
  employer: EmployerResponse;
  pay_date: string;
  gross_wages: DecimalString;
  bonus: DecimalString;
  taxable_wages: DecimalString;
  federal_withholding: DecimalString;
  social_security: DecimalString;
  medicare: DecimalString;
  total_taxes_withheld: DecimalString;
  total_pretax_deductions: DecimalString;
  total_posttax_deductions: DecimalString;
  net_pay: DecimalString;
  notes: string | null;
}

export interface PaycheckCreate {
  employer_id: number;
  pay_date: string;
  gross_wages: string;
  bonus?: string;
  federal_withholding?: string;
  social_security?: string;
  medicare?: string;
  deduction_401k?: string;
  deduction_403b?: string;
  deduction_health_insurance?: string;
  deduction_dental_insurance?: string;
  deduction_vision_insurance?: string;
  deduction_hsa?: string;
  deduction_fsa?: string;
  deduction_dependent_care_fsa?: string;
  deduction_commuter?: string;
  deduction_other_pretax?: string;
  deduction_roth_401k?: string;
  deduction_roth_403b?: string;
  deduction_other_posttax?: string;
  notes?: string | null;
}

export interface Retirement1099RResponse {
  id: number;
  pay_date: string;
  gross_amount: DecimalString;
  pretax_deductions: DecimalString;
  posttax_deductions: DecimalString;
  taxable_amount: DecimalString;
  federal_withholding: DecimalString;
  net_amount: DecimalString;
  source_description: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Retirement1099RCreate {
  pay_date: string;
  gross_amount: string;
  pretax_deductions?: string;
  posttax_deductions?: string;
  federal_withholding?: string;
  source_description?: string | null;
  notes?: string | null;
}

export interface NonTaxableIncomeResponse {
  id: number;
  pay_date: string;
  amount: DecimalString;
  source_type: string | null;
  notes: string | null;
}

export interface NonTaxableIncomeCreate {
  pay_date: string;
  amount: string;
  source_type?: string | null;
  notes?: string | null;
}

export interface AvailableYearsResponse {
  available_years: number[];
  latest_year: number | null;
  data_directory: string;
}

export interface DeleteResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// Tax calculation
// ---------------------------------------------------------------------------

export type FilingStatus = "single" | "married_filing_jointly" | "married_filing_separately" | "head_of_household";

export interface TaxCalculationRequest {
  w2_gross_income?: string;
  pension_gross_income?: string;
  filing_status: FilingStatus;
  age_65_plus?: boolean;
  num_children?: number;
  use_standard_deduction?: boolean;
  itemized_deduction_amount?: string | null;
  retirement_pretax_deductions?: string;
  non_taxable_income?: string;
  tax_year?: number;
}

export interface BracketBreakdown {
  bracket: string;
  rate: number;
  taxable_income_in_bracket: number;
  tax_in_bracket: number;
}

export interface TaxCalculationResponse {
  gross_income: DecimalString;
  retirement_pretax_deductions: DecimalString;
  adjusted_gross_income: DecimalString;
  deduction_amount: DecimalString;
  deduction_type: string;
  taxable_income: DecimalString;
  federal_tax_owed: DecimalString;
  child_tax_credits: DecimalString;
  total_tax_liability: DecimalString;
  effective_tax_rate: DecimalString;
  marginal_tax_rate: DecimalString;
  breakdown_by_bracket: BracketBreakdown[];
  fica_taxes: Record<string, DecimalString>;
  total_household_income: DecimalString;
  notes: string[];
}

export interface TaxReconciliationResponse extends TaxCalculationResponse {
  tax_year: number;
  filing_status: FilingStatus;
  num_children: number;
  w2_gross: DecimalString;
  w2_pretax_deductions: DecimalString;
  w2_taxable: DecimalString;
  pension_gross: DecimalString;
  pension_pretax_deductions: DecimalString;
  pension_taxable: DecimalString;
  non_taxable_income: DecimalString;
  total_taxable_income: DecimalString;
  total_federal_withheld: DecimalString;
  total_fica_withheld: DecimalString;
  total_withheld: DecimalString;
  combined_liability: DecimalString;
  refund_or_owed: DecimalString;
  overpayment_percentage: DecimalString;
  result_status: string;
}

// ---------------------------------------------------------------------------
// W-4 optimization
// ---------------------------------------------------------------------------

export interface W4OptimizeRequest {
  total_annual_w2_income: string;
  paychecks_per_year: number;
  filing_status: FilingStatus;
  num_children?: number;
  other_annual_income?: string;
  itemized_deductions?: string;
  target_refund?: string;
  year?: number;
}

export interface W4Recommendation {
  employer_name: string;
  filing_status: string;
  step2_checkbox: boolean;
  step2_note: string;
  step3_amount: DecimalString;
  step3_explanation: string;
  step4a_other_income: DecimalString;
  step4a_explanation: string;
  step4b_deductions: DecimalString;
  step4b_explanation: string;
  step4c_extra_withholding: DecimalString;
  step4c_explanation: string;
  expected_annual_withholding: DecimalString;
  expected_paychecks_per_year: number;
}

export interface W4OptimizeResponse {
  year: number;
  filing_status: string;
  total_w2_income: DecimalString;
  total_pension_income: DecimalString;
  total_va_income: DecimalString;
  total_taxable_income: DecimalString;
  estimated_tax_liability: DecimalString;
  target_refund: DecimalString;
  target_total_withholding: DecimalString;
  current_total_withholding: DecimalString;
  current_refund_or_owed: DecimalString;
  adjustment_needed: DecimalString;
  w4_recommendations: W4Recommendation[];
  notes: string[];
}

export interface EmployerRemainingOverride {
  employer_id: number;
  expected_remaining_gross_per_paycheck: DecimalString;
}

export interface MidYearDBW4OptimizeRequest {
  tax_year: number;
  filing_status: FilingStatus;
  as_of_date?: string;
  remaining_pay_periods: number;
  remaining_pension_periods?: number;
  remaining_non_taxable_periods?: number;
  num_children?: number;
  target_refund?: DecimalString;
  use_standard_deduction?: boolean;
  itemized_deductions?: DecimalString;
  expected_remaining_pension_taxable?: DecimalString;
  employer_overrides?: EmployerRemainingOverride[];
}

export interface MidYearPeriodSuggestionRequest {
  tax_year: number;
  as_of_date?: string;
  w2_pay_frequency: "weekly" | "biweekly" | "semimonthly" | "monthly";
}

export interface MidYearEmployerSummary {
  employer_id: number;
  employer_name: string;
  paychecks_recorded: number;
  ytd_gross: DecimalString;
  ytd_pretax_deductions: DecimalString;
  ytd_federal_withholding: DecimalString;
  projected_remaining_gross: DecimalString;
  projected_annual_gross: DecimalString;
}

export interface MidYearYTDSummary {
  tax_year: number;
  as_of_date: string | null;
  remaining_pay_periods: number;
  remaining_w2_pay_periods: number;
  remaining_pension_periods: number;
  remaining_non_taxable_periods: number;
  employers: MidYearEmployerSummary[];
  ytd_pension_taxable: DecimalString;
  ytd_pension_federal_withholding: DecimalString;
  ytd_non_taxable_income: DecimalString;
  ytd_total_federal_withholding: DecimalString;
}

export interface MidYearProjectionSummary {
  projected_remaining_pension_taxable: DecimalString;
  projected_full_year_pension_taxable: DecimalString;
  projected_full_year_non_taxable_income: DecimalString;
  projected_remaining_w2_withholding: DecimalString;
  projected_remaining_pension_withholding: DecimalString;
  projected_annual_w2_withholding: DecimalString;
  projected_annual_pension_withholding: DecimalString;
  projected_annual_total_withholding: DecimalString;
}

export interface MidYearPeriodSuggestionResponse {
  tax_year: number;
  as_of_date: string;
  w2_pay_frequency: "weekly" | "biweekly" | "semimonthly" | "monthly";
  remaining_pay_periods: number;
  remaining_pension_periods: number;
  remaining_non_taxable_periods: number;
  monthly_baseline_periods: number;
  current_month_has_pension_entry: boolean;
  current_month_has_non_taxable_entry: boolean;
  notes: string[];
}

export interface MidYearW4OptimizeResponse extends W4OptimizeResponse {
  ytd_summary: MidYearYTDSummary;
  projection_summary: MidYearProjectionSummary;
  assumptions: string[];
}

export interface WithholdingCalcRequest {
  gross_pay_per_paycheck: string;
  pay_frequency: string;
  filing_status: FilingStatus;
  multiple_jobs_checkbox?: boolean;
  dependents_amount?: string;
  other_income_annual?: string;
  deductions_annual?: string;
  extra_withholding?: string;
  year?: number;
}

export interface WithholdingCalcResponse {
  gross_pay: DecimalString;
  withholding_amount: DecimalString;
  pay_frequency: string;
  annualized_gross: DecimalString;
  annualized_withholding: DecimalString;
  effective_rate: DecimalString;
}

// ---------------------------------------------------------------------------
// Projections
// ---------------------------------------------------------------------------

export interface ProjectYearRequest {
  projection_year?: number;
  filing_status: FilingStatus;
  num_children?: number;
  w2_gross?: string;
  w2_pretax_deductions?: string;
  pension_gross?: string;
  pension_pretax_deductions?: string;
  va_disability?: string;
  use_standard_deduction?: boolean;
  itemized_deduction_amount?: string;
}

export interface ProjectYearResponse {
  year: number;
  filing_status: string;
  w2_gross: DecimalString;
  w2_taxable: DecimalString;
  pension_taxable: DecimalString;
  total_taxable_income: DecimalString;
  taxable_income: DecimalString;
  federal_tax_liability: DecimalString;
  fica_liability: DecimalString;
  total_tax_liability: DecimalString;
  estimated_withholding: DecimalString;
  estimated_refund_or_owed: DecimalString;
  effective_rate: DecimalString;
  marginal_rate: DecimalString;
}

export interface CompareYearsRequest {
  base_year?: number;
  comparison_year?: number;
  filing_status: FilingStatus;
  num_children?: number;
  base_w2_gross: string;
  comparison_w2_gross: string;
  base_pension?: string;
  comparison_pension?: string;
}

export interface YearComparisonEntry {
  from_year: number;
  to_year: number;
  income_change: { amount: number; percentage: number };
  tax_change: { amount: number; percentage: number };
  effective_rate_change: { amount: number; from: number; to: number };
  marginal_bracket_change: { from: number; to: number; moved_bracket: boolean };
}

export interface CompareYearsResponse {
  projections: ProjectYearResponse[];
  comparisons: YearComparisonEntry[];
  summary: {
    years_compared: number;
    total_income_change: number;
    total_tax_change: number;
  };
}
