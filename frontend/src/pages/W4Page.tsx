import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { apiClient } from "../lib/api/client";
import type {
  EmployerRemainingOverride,
  FilingStatus,
  MidYearDBW4OptimizeRequest,
  MidYearPeriodSuggestionRequest,
  MidYearW4OptimizeResponse,
  W4OptimizeRequest,
  W4OptimizeResponse,
  WithholdingCalcRequest,
} from "../lib/api/types";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();

const FILING_STATUSES: { value: FilingStatus; label: string }[] = [
  { value: "single", label: "Single" },
  { value: "married_filing_jointly", label: "Married Filing Jointly" },
  { value: "married_filing_separately", label: "Married Filing Separately" },
  { value: "head_of_household", label: "Head of Household" },
];

const PAY_FREQUENCIES = [
  { value: "weekly", label: "Weekly (52×/yr)" },
  { value: "biweekly", label: "Biweekly (26×/yr)" },
  { value: "semimonthly", label: "Semi-monthly (24×/yr)" },
  { value: "monthly", label: "Monthly (12×/yr)" },
];

const frequencyToCount = (freq: string): number =>
  ({ weekly: 52, biweekly: 26, semimonthly: 24, monthly: 12 })[freq] ?? 26;

// ---------------------------------------------------------------------------
// W-4 optimizer result display
// ---------------------------------------------------------------------------

const W4ResultCard = ({ result }: { result: W4OptimizeResponse }) => (
  <div className="card result-card">
    <h3 className="card-title">W-4 Optimization — {result.year}</h3>

    <div className="result-grid mb-4">
      <div className="result-row">
        <span>Estimated total tax liability</span>
        <strong>{formatCurrency(parseDecimalString(result.estimated_tax_liability))}</strong>
      </div>
      <div className="result-row">
        <span>Target total withholding</span>
        <strong>{formatCurrency(parseDecimalString(result.target_total_withholding))}</strong>
      </div>
      <div className="result-row result-divider">
        <span>Additional annual W-2 withholding needed</span>
        <strong
          className={
            parseDecimalString(result.adjustment_needed) > 0
              ? "text-owed"
              : parseDecimalString(result.adjustment_needed) < 0
                ? "text-refund"
                : ""
          }
        >
          {formatCurrency(Math.abs(parseDecimalString(result.adjustment_needed)))}
        </strong>
      </div>
      <div className="result-row">
        <span>Direction</span>
        <strong
          className={
            parseDecimalString(result.adjustment_needed) > 0
              ? "text-owed"
              : parseDecimalString(result.adjustment_needed) < 0
                ? "text-refund"
                : ""
          }
        >
          {parseDecimalString(result.adjustment_needed) > 0
            ? "Need to withhold more from W-2 paychecks"
            : parseDecimalString(result.adjustment_needed) < 0
              ? "Can withhold less from W-2 paychecks"
              : "Withholding is on target"}
        </strong>
      </div>
    </div>

    <p className="helper-text">
      This recommendation uses your total projected tax picture, but the lever you can change here is W-2 withholding.
      Pension income is included in the calculation and can be audited in the projection details.
    </p>

    {result.w4_recommendations.map((rec) => (
      <div key={rec.employer_name} className="w4-rec-card">
        <h4 className="w4-rec-title">{rec.employer_name}</h4>

        <div className="w4-steps">
          <div className="w4-step">
            <span className="w4-step-label">Step 2 — Multiple jobs</span>
            <span className="w4-step-value">{rec.step2_checkbox ? "Check the box" : "Leave blank"}</span>
            {rec.step2_note && <p className="w4-step-note">{rec.step2_note}</p>}
          </div>

          <div className="w4-step">
            <span className="w4-step-label">Step 3 — Dependents</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step3_amount))}</span>
            {rec.step3_explanation && <p className="w4-step-note">{rec.step3_explanation}</p>}
          </div>

          <div className="w4-step">
            <span className="w4-step-label">Step 4a — Other income / pension</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step4a_other_income))}</span>
            {rec.step4a_explanation && <p className="w4-step-note">{rec.step4a_explanation}</p>}
          </div>

          <div className="w4-step">
            <span className="w4-step-label">Step 4b — Deductions</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step4b_deductions))}</span>
            {rec.step4b_explanation && <p className="w4-step-note">{rec.step4b_explanation}</p>}
          </div>

          <div className="w4-step result-highlight">
            <span className="w4-step-label">Step 4c — Extra per paycheck (W-2 only)</span>
            <span
              className={`w4-step-value ${
                parseDecimalString(rec.step4c_extra_withholding) > 0 ? "text-owed" : "text-refund"
              }`}
            >
              {formatCurrency(parseDecimalString(rec.step4c_extra_withholding))}
            </span>
            {rec.step4c_explanation && <p className="w4-step-note">{rec.step4c_explanation}</p>}
          </div>

          <div className="w4-step">
            <span className="w4-step-label">Expected annual withholding</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.expected_annual_withholding))}</span>
          </div>
        </div>
      </div>
    ))}

    {result.notes.length > 0 && (
      <ul className="result-notes">
        {result.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// W-4 optimizer tab
// ---------------------------------------------------------------------------

const OptimizerTab = () => {
  const [fields, setFields] = useState<W4OptimizeRequest>({
    total_annual_w2_income: "",
    paychecks_per_year: 26,
    filing_status: "single",
    num_children: 0,
    other_annual_income: "0",
    itemized_deductions: "0",
    target_refund: "0",
    year: currentYear,
  });

  const [payFreq, setPayFreq] = useState("biweekly");

  const mutation = useMutation({
    mutationFn: (data: W4OptimizeRequest) => apiClient.optimizeW4(data),
  });

  const set = <K extends keyof W4OptimizeRequest>(key: K, val: W4OptimizeRequest[K]) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">W-4 Optimizer</h2>
      </div>

      <form
        className="card income-form mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(fields);
        }}
      >
        <div className="form-grid">
          <label className="form-label">
            Tax year
            <select className="form-input" value={fields.year} onChange={(e) => set("year", Number(e.target.value))}>
              {Array.from({ length: 4 }, (_, i) => currentYear - i + 1).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Filing status
            <select
              className="form-input"
              value={fields.filing_status}
              onChange={(e) => set("filing_status", e.target.value as FilingStatus)}
            >
              {FILING_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Annual W-2 gross wages
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.total_annual_w2_income}
              onChange={(e) => set("total_annual_w2_income", e.target.value)}
              required
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Pay frequency
            <select
              className="form-input"
              value={payFreq}
              onChange={(e) => {
                setPayFreq(e.target.value);
                set("paychecks_per_year", frequencyToCount(e.target.value));
              }}
            >
              {PAY_FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Annual pension / other taxable income
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.other_annual_income}
              onChange={(e) => set("other_annual_income", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Qualifying children
            <input
              type="number"
              min="0"
              max="20"
              className="form-input"
              value={fields.num_children}
              onChange={(e) => set("num_children", Number(e.target.value))}
            />
          </label>

          <label className="form-label">
            Itemized deductions (0 = standard)
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.itemized_deductions}
              onChange={(e) => set("itemized_deductions", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Target refund (0 = break even)
            <input
              type="number"
              step="0.01"
              className="form-input"
              value={fields.target_refund}
              onChange={(e) => set("target_refund", e.target.value)}
              placeholder="0.00"
            />
          </label>
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Optimizing…" : "Optimize W-4"}
        </button>
      </form>

      {mutation.data && <W4ResultCard result={mutation.data} />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Mid-year optimizer tab
// ---------------------------------------------------------------------------

const MidYearResultDetails = ({ result }: { result: MidYearW4OptimizeResponse }) => {
  const sumDecimals = (values: string[]) => values.reduce((total, value) => total + parseDecimalString(value), 0);

  const ytdPension = parseDecimalString(result.ytd_summary.ytd_pension_taxable);
  const remainingPension = parseDecimalString(result.projection_summary.projected_remaining_pension_taxable);
  const annualPension = parseDecimalString(result.projection_summary.projected_full_year_pension_taxable);
  const ytdNonTaxable = parseDecimalString(result.ytd_summary.ytd_non_taxable_income);
  const annualNonTaxable = parseDecimalString(result.projection_summary.projected_full_year_non_taxable_income);
  const remainingNonTaxable = annualNonTaxable - ytdNonTaxable;

  const ytdW2Gross = sumDecimals(result.ytd_summary.employers.map((employer) => employer.ytd_gross));
  const projectedAnnualW2Gross = sumDecimals(
    result.ytd_summary.employers.map((employer) => employer.projected_annual_gross),
  );
  const projectedRemainingW2Gross = projectedAnnualW2Gross - ytdW2Gross;
  const ytdW2Pretax = sumDecimals(result.ytd_summary.employers.map((employer) => employer.ytd_pretax_deductions));

  const ytdW2Withholding =
    parseDecimalString(result.ytd_summary.ytd_total_federal_withholding) -
    parseDecimalString(result.ytd_summary.ytd_pension_federal_withholding);
  const ytdPensionWithholding = parseDecimalString(result.ytd_summary.ytd_pension_federal_withholding);
  const projectedRemainingW2Withholding = parseDecimalString(
    result.projection_summary.projected_remaining_w2_withholding,
  );
  const remainingPensionWithholding = parseDecimalString(
    result.projection_summary.projected_remaining_pension_withholding,
  );
  const annualW2Withholding = parseDecimalString(result.projection_summary.projected_annual_w2_withholding);
  const annualPensionWithholding = parseDecimalString(result.projection_summary.projected_annual_pension_withholding);
  const annualTotalWithholding = parseDecimalString(result.projection_summary.projected_annual_total_withholding);
  const estimatedTaxLiability = parseDecimalString(result.estimated_tax_liability);
  const projectedTaxBalance = annualTotalWithholding - estimatedTaxLiability;
  const projectedTaxBalanceLabel = projectedTaxBalance >= 0 ? "Refund estimate" : "Amount owed";
  const projectedTaxBalanceClass = projectedTaxBalance >= 0 ? "text-refund" : "text-owed";
  const projectedTaxBalanceHelper =
    projectedTaxBalance >= 0
      ? "Your projected withholding exceeds your projected tax liability. The difference should come back as a refund after filing."
      : "Your projected withholding is below your projected tax liability. You will owe this amount at tax time unless you adjust your W-4.";

  return (
    <div className="card result-card mt-2">
      <h3 className="card-title">Year-to-Date Summary</h3>

      <div className="result-grid mb-4">
        <div className="result-row">
          <span>As-of date</span>
          <strong>{result.ytd_summary.as_of_date ?? "All records for tax year"}</strong>
        </div>
        <div className="result-row">
          <span>Remaining periods in use</span>
          <strong>
            W-2 {result.ytd_summary.remaining_w2_pay_periods} • Pension {result.ytd_summary.remaining_pension_periods} •
            Non-taxable {result.ytd_summary.remaining_non_taxable_periods}
          </strong>
        </div>
        <div className="result-row">
          <span>YTD total federal withholding</span>
          <strong>{formatCurrency(parseDecimalString(result.ytd_summary.ytd_total_federal_withholding))}</strong>
        </div>
      </div>

      <p className="helper-text">
        The W-4 recommendation below is based on the total tax picture. The sections below keep W-2, pension, and
        non-taxable income separated so the rollup is easier to audit.
      </p>

      <h4 className="w4-rec-title">W-2 Projection Summary</h4>
      <div className="result-grid mb-4">
        <div className="result-row">
          <span>YTD W-2 gross</span>
          <strong>{formatCurrency(ytdW2Gross)}</strong>
        </div>
        <div className="result-row">
          <span>YTD W-2 pretax deductions</span>
          <strong>{formatCurrency(ytdW2Pretax)}</strong>
        </div>
        <div className="result-row">
          <span>Projected remaining W-2 gross</span>
          <strong>{formatCurrency(projectedRemainingW2Gross)}</strong>
        </div>
        <div className="result-row result-divider">
          <span>Projected annual W-2 gross</span>
          <strong>{formatCurrency(projectedAnnualW2Gross)}</strong>
        </div>
        <div className="result-row">
          <span>YTD W-2 withholding</span>
          <strong>{formatCurrency(ytdW2Withholding)}</strong>
        </div>
        <div className="result-row">
          <span>Projected remaining W-2 withholding</span>
          <strong>{formatCurrency(projectedRemainingW2Withholding)}</strong>
        </div>
        <div className="result-row result-divider">
          <span>Projected annual W-2 withholding</span>
          <strong>{formatCurrency(annualW2Withholding)}</strong>
        </div>
      </div>

      {result.ytd_summary.employers.length === 0 ? (
        <p className="helper-text">No paycheck records found for the selected year and as-of date.</p>
      ) : (
        <div className="midyear-grid mb-4">
          {result.ytd_summary.employers.map((employer) => (
            <article key={employer.employer_id} className="w4-rec-card midyear-employer-card">
              <h5 className="midyear-employer-title">{employer.employer_name}</h5>
              <p className="helper-text midyear-meta">Paychecks recorded: {employer.paychecks_recorded}</p>
              <div className="equation-grid">
                <div className="equation-cell">
                  <span>YTD gross</span>
                  <strong>{formatCurrency(parseDecimalString(employer.ytd_gross))}</strong>
                </div>
                <div className="equation-operator">+</div>
                <div className="equation-cell">
                  <span>Projected remaining</span>
                  <strong>{formatCurrency(parseDecimalString(employer.projected_remaining_gross))}</strong>
                </div>
                <div className="equation-operator">=</div>
                <div className="equation-cell equation-total">
                  <span>Projected annual gross</span>
                  <strong>{formatCurrency(parseDecimalString(employer.projected_annual_gross))}</strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <h4 className="w4-rec-title">Pension Projection Summary</h4>
      <div className="equation-grid mb-4">
        <div className="equation-cell">
          <span>YTD pension taxable</span>
          <strong>{formatCurrency(ytdPension)}</strong>
        </div>
        <div className="equation-operator">+</div>
        <div className="equation-cell">
          <span>Projected remaining pension</span>
          <strong>{formatCurrency(remainingPension)}</strong>
        </div>
        <div className="equation-operator">=</div>
        <div className="equation-cell equation-total">
          <span>Projected full-year pension</span>
          <strong>{formatCurrency(annualPension)}</strong>
        </div>
      </div>

      <h4 className="w4-rec-title">Non-taxable Projection Summary</h4>
      <div className="equation-grid mb-4">
        <div className="equation-cell">
          <span>YTD non-taxable income</span>
          <strong>{formatCurrency(ytdNonTaxable)}</strong>
        </div>
        <div className="equation-operator">+</div>
        <div className="equation-cell">
          <span>Projected remaining non-taxable</span>
          <strong>{formatCurrency(remainingNonTaxable)}</strong>
        </div>
        <div className="equation-operator">=</div>
        <div className="equation-cell equation-total">
          <span>Projected full-year non-taxable</span>
          <strong>{formatCurrency(annualNonTaxable)}</strong>
        </div>
      </div>

      <h4 className="w4-rec-title">W-2 Federal Withholding Projection</h4>
      <div className="equation-grid mb-4">
        <div className="equation-cell">
          <span>YTD federal withholding</span>
          <strong>{formatCurrency(ytdW2Withholding)}</strong>
        </div>
        <div className="equation-operator">+</div>
        <div className="equation-cell">
          <span>Projected remaining</span>
          <strong>{formatCurrency(projectedRemainingW2Withholding)}</strong>
        </div>
        <div className="equation-operator">=</div>
        <div className="equation-cell equation-total">
          <span>Projected annual</span>
          <strong>{formatCurrency(annualW2Withholding)}</strong>
        </div>
      </div>

      <h4 className="w4-rec-title">Pension Federal Withholding Projection</h4>
      <div className="equation-grid mb-4">
        <div className="equation-cell">
          <span>YTD federal withholding</span>
          <strong>{formatCurrency(ytdPensionWithholding)}</strong>
        </div>
        <div className="equation-operator">+</div>
        <div className="equation-cell">
          <span>Projected remaining</span>
          <strong>{formatCurrency(remainingPensionWithholding)}</strong>
        </div>
        <div className="equation-operator">=</div>
        <div className="equation-cell equation-total">
          <span>Projected annual</span>
          <strong>{formatCurrency(annualPensionWithholding)}</strong>
        </div>
      </div>

      <h4 className="w4-rec-title">Projected Total Federal Withholding</h4>
      <div className="result-row" style={{ fontSize: "1.1em", fontWeight: "bold", padding: "0.75rem 0" }}>
        <span>W-2 + Pension</span>
        <strong className="text-good">{formatCurrency(annualTotalWithholding)}</strong>
      </div>

      <h4 className="w4-rec-title" style={{ marginTop: "1.5rem" }}>
        Projected Tax Rollup
      </h4>
      <div className="equation-grid mb-4">
        <div className="equation-cell">
          <span>Estimated annual tax liability</span>
          <strong>{formatCurrency(estimatedTaxLiability)}</strong>
        </div>
        <div className="equation-operator">−</div>
        <div className="equation-cell">
          <span>Projected annual withholding</span>
          <strong>{formatCurrency(annualTotalWithholding)}</strong>
        </div>
        <div className="equation-operator">=</div>
        <div className="equation-cell equation-total">
          <span>{projectedTaxBalanceLabel}</span>
          <strong className={projectedTaxBalanceClass}>{formatCurrency(Math.abs(projectedTaxBalance))}</strong>
        </div>
      </div>
      <p className="helper-text">{projectedTaxBalanceHelper}</p>
      <p className="helper-text">This rollup is what drives the W-4 recommendation below.</p>

      {result.assumptions.length > 0 && (
        <>
          <h4 className="w4-rec-title">Assumptions</h4>
          <ul className="result-notes">
            {result.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
};

const MidYearTab = () => {
  type OverrideRow = EmployerRemainingOverride & { row_id: string };

  const createOverrideRow = (): OverrideRow => ({
    row_id: crypto.randomUUID(),
    employer_id: 0,
    expected_remaining_gross_per_paycheck: "",
  });

  const [fields, setFields] = useState<MidYearDBW4OptimizeRequest>(() => {
    return {
      tax_year: currentYear,
      filing_status: "single",
      remaining_pay_periods: 1,
      remaining_pension_periods: 1,
      remaining_non_taxable_periods: 1,
      num_children: 0,
      target_refund: "0",
      use_standard_deduction: true,
      itemized_deductions: "0",
      employer_overrides: [],
    };
  });
  const [asOfDate, setAsOfDate] = useState("");
  const [expectedRemainingPensionTaxable, setExpectedRemainingPensionTaxable] = useState("");
  const [w2PayFrequency, setW2PayFrequency] = useState<"weekly" | "biweekly" | "semimonthly" | "monthly">("biweekly");
  const [employerOverrides, setEmployerOverrides] = useState<OverrideRow[]>([]);

  const employersQuery = useQuery({
    queryKey: ["midyear-employers"],
    queryFn: apiClient.listEmployers,
  });

  const suggestionMutation = useMutation({
    mutationFn: (data: MidYearPeriodSuggestionRequest) => apiClient.suggestMidyearPeriods(data),
  });

  const mutation = useMutation({
    mutationFn: (data: MidYearDBW4OptimizeRequest) => apiClient.optimizeMidyearW4(data),
  });

  const set = useCallback(<K extends keyof MidYearDBW4OptimizeRequest>(key: K, val: MidYearDBW4OptimizeRequest[K]) => {
    setFields((prev) => ({ ...prev, [key]: val }));
  }, []);

  const fetchSuggestedPeriods = useCallback(
    async (suggestionDate?: string) => {
      try {
        const suggestion = await suggestionMutation.mutateAsync({
          tax_year: fields.tax_year,
          as_of_date: suggestionDate || undefined,
          w2_pay_frequency: w2PayFrequency,
        });

        set("remaining_pay_periods", suggestion.remaining_pay_periods);
        set("remaining_pension_periods", suggestion.remaining_pension_periods);
        set("remaining_non_taxable_periods", suggestion.remaining_non_taxable_periods);
      } catch {
        // Keep the current values if the backend suggestion call fails.
      }
    },
    [fields.tax_year, set, suggestionMutation.mutateAsync, w2PayFrequency],
  );

  useEffect(() => {
    void fetchSuggestedPeriods();
  }, [fetchSuggestedPeriods]);

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Mid-Year W-4 Optimizer (Database-Backed)</h2>
      </div>

      <form
        className="card income-form mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          const payload: MidYearDBW4OptimizeRequest = {
            ...fields,
            as_of_date: asOfDate || undefined,
            expected_remaining_pension_taxable: expectedRemainingPensionTaxable || undefined,
            itemized_deductions: fields.use_standard_deduction ? "0" : (fields.itemized_deductions ?? "0"),
            employer_overrides: employerOverrides
              .filter((override) => override.employer_id > 0 && override.expected_remaining_gross_per_paycheck !== "")
              .map((override) => ({
                employer_id: override.employer_id,
                expected_remaining_gross_per_paycheck: override.expected_remaining_gross_per_paycheck,
              })),
            remaining_pension_periods: fields.remaining_pension_periods ?? fields.remaining_pay_periods,
            remaining_non_taxable_periods: fields.remaining_non_taxable_periods ?? fields.remaining_pay_periods,
          };

          mutation.mutate(payload);
        }}
      >
        <p className="helper-text">
          Uses year-to-date entries from your database, projects the remaining year, and recommends W-4 adjustments.
        </p>
        <p className="helper-text">
          Remaining periods are editable. Auto-suggest now comes from the backend so the same rules are used everywhere.
        </p>

        <div className="midyear-autosuggest card">
          <div className="panel-header">
            <h3 className="panel-title">Auto-suggest Remaining Periods</h3>
          </div>
          <div className="midyear-override-row">
            <label className="form-label">
              W-2 pay frequency
              <select
                className="form-input"
                value={w2PayFrequency}
                onChange={(e) => setW2PayFrequency(e.target.value as "weekly" | "biweekly" | "semimonthly" | "monthly")}
              >
                {PAY_FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="midyear-autosuggest-action">
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  void fetchSuggestedPeriods(asOfDate || undefined);
                }}
                disabled={suggestionMutation.isPending}
              >
                {suggestionMutation.isPending ? "Suggesting…" : "Auto-suggest"}
              </button>
            </div>
          </div>
        </div>

        <div className="form-grid">
          <label className="form-label">
            Tax year
            <select
              className="form-input"
              value={fields.tax_year}
              onChange={(e) => set("tax_year", Number(e.target.value))}
            >
              {Array.from({ length: 4 }, (_, i) => currentYear - i + 1).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Filing status
            <select
              className="form-input"
              value={fields.filing_status}
              onChange={(e) => set("filing_status", e.target.value as FilingStatus)}
            >
              {FILING_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            As-of date (optional)
            <input type="date" className="form-input" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} />
          </label>

          <label className="form-label">
            Remaining W-2 pay periods
            <input
              type="number"
              min="1"
              className="form-input"
              value={fields.remaining_pay_periods}
              onChange={(e) => set("remaining_pay_periods", Number(e.target.value))}
              required
            />
          </label>

          <label className="form-label">
            Remaining pension periods (monthly typical)
            <input
              type="number"
              min="1"
              className="form-input"
              value={fields.remaining_pension_periods ?? fields.remaining_pay_periods}
              onChange={(e) => set("remaining_pension_periods", Number(e.target.value))}
              required
            />
          </label>

          <label className="form-label">
            Remaining non-taxable periods (monthly typical)
            <input
              type="number"
              min="1"
              className="form-input"
              value={fields.remaining_non_taxable_periods ?? fields.remaining_pay_periods}
              onChange={(e) => set("remaining_non_taxable_periods", Number(e.target.value))}
              required
            />
          </label>

          <label className="form-label">
            Qualifying children
            <input
              type="number"
              min="0"
              max="20"
              className="form-input"
              value={fields.num_children ?? 0}
              onChange={(e) => set("num_children", Number(e.target.value))}
            />
          </label>

          <label className="form-label">
            Target refund (0 = break even)
            <input
              type="number"
              step="0.01"
              className="form-input"
              value={fields.target_refund ?? "0"}
              onChange={(e) => set("target_refund", e.target.value)}
            />
          </label>

          <label className="form-label">
            Expected remaining pension taxable (optional)
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={expectedRemainingPensionTaxable}
              onChange={(e) => setExpectedRemainingPensionTaxable(e.target.value)}
              placeholder="Auto-project from YTD if blank"
            />
          </label>

          <label
            className="form-label"
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <input
              type="checkbox"
              checked={fields.use_standard_deduction ?? true}
              onChange={(e) => set("use_standard_deduction", e.target.checked)}
            />
            Use standard deduction
          </label>

          {!(fields.use_standard_deduction ?? true) && (
            <label className="form-label">
              Itemized deductions
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.itemized_deductions ?? "0"}
                onChange={(e) => set("itemized_deductions", e.target.value)}
              />
            </label>
          )}
        </div>

        <div className="midyear-override-section">
          <div className="panel-header">
            <h3 className="panel-title">Employer Gross Overrides (Optional)</h3>
          </div>
          <p className="helper-text">
            Override projected remaining gross per paycheck for a specific employer when YTD averages are not accurate.
          </p>

          {employersQuery.isError && <p className="form-error">Unable to load employers for overrides.</p>}

          {employerOverrides.map((override) => (
            <div key={override.row_id} className="midyear-override-row">
              <select
                className="form-input"
                value={override.employer_id}
                onChange={(e) => {
                  const value = Number(e.target.value);
                  setEmployerOverrides((prev) =>
                    prev.map((row) => (row.row_id === override.row_id ? { ...row, employer_id: value } : row)),
                  );
                }}
              >
                <option value={0}>Select employer</option>
                {(employersQuery.data ?? []).map((employer) => (
                  <option key={employer.id} value={employer.id}>
                    {employer.name}
                  </option>
                ))}
              </select>

              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={override.expected_remaining_gross_per_paycheck}
                onChange={(e) => {
                  const value = e.target.value;
                  setEmployerOverrides((prev) =>
                    prev.map((row) =>
                      row.row_id === override.row_id
                        ? {
                            ...row,
                            expected_remaining_gross_per_paycheck: value,
                          }
                        : row,
                    ),
                  );
                }}
                placeholder="Remaining gross/paycheck"
              />

              <button
                type="button"
                className="btn-ghost"
                onClick={() => setEmployerOverrides((prev) => prev.filter((row) => row.row_id !== override.row_id))}
              >
                Remove
              </button>
            </div>
          ))}

          <button
            type="button"
            className="btn-ghost"
            onClick={() => setEmployerOverrides((prev) => [...prev, createOverrideRow()])}
            disabled={employersQuery.isLoading}
          >
            Add employer override
          </button>
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Optimizing…" : "Optimize Mid-Year W-4"}
        </button>
      </form>

      {mutation.data && (
        <>
          <MidYearResultDetails result={mutation.data} />
          <W4ResultCard result={mutation.data} />
        </>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Withholding calculator tab
// ---------------------------------------------------------------------------

const WithholdingTab = () => {
  const [fields, setFields] = useState<WithholdingCalcRequest>({
    gross_pay_per_paycheck: "",
    pay_frequency: "biweekly",
    filing_status: "single",
    multiple_jobs_checkbox: false,
    dependents_amount: "0",
    other_income_annual: "0",
    deductions_annual: "0",
    extra_withholding: "0",
    year: currentYear,
  });

  const mutation = useMutation({
    mutationFn: (data: WithholdingCalcRequest) => apiClient.calculateWithholding(data),
  });

  const set = <K extends keyof WithholdingCalcRequest>(key: K, val: WithholdingCalcRequest[K]) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Per-Paycheck Withholding Calculator</h2>
      </div>

      <form
        className="card income-form mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(fields);
        }}
      >
        <p className="helper-text">
          Calculates withholding using the IRS Publication 15-T percentage method based on current W-4 settings.
        </p>

        <div className="form-grid">
          <label className="form-label">
            Tax year
            <select className="form-input" value={fields.year} onChange={(e) => set("year", Number(e.target.value))}>
              {Array.from({ length: 4 }, (_, i) => currentYear - i + 1).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Gross pay per paycheck
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.gross_pay_per_paycheck}
              onChange={(e) => set("gross_pay_per_paycheck", e.target.value)}
              required
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Pay frequency
            <select
              className="form-input"
              value={fields.pay_frequency}
              onChange={(e) => set("pay_frequency", e.target.value)}
            >
              {PAY_FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Filing status (W-4 Step 1)
            <select
              className="form-input"
              value={fields.filing_status}
              onChange={(e) => set("filing_status", e.target.value as FilingStatus)}
            >
              {FILING_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Step 3 — Dependents amount
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.dependents_amount}
              onChange={(e) => set("dependents_amount", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Step 4a — Other annual income
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.other_income_annual}
              onChange={(e) => set("other_income_annual", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Step 4b — Annual deductions
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.deductions_annual}
              onChange={(e) => set("deductions_annual", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Step 4c — Extra per paycheck
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.extra_withholding}
              onChange={(e) => set("extra_withholding", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label
            className="form-label"
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <input
              type="checkbox"
              checked={fields.multiple_jobs_checkbox}
              onChange={(e) => set("multiple_jobs_checkbox", e.target.checked)}
            />
            Step 2 — Multiple jobs checkbox
          </label>
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Calculating…" : "Calculate withholding"}
        </button>
      </form>

      {mutation.data && (
        <div className="card result-card">
          <h3 className="card-title">Withholding Result</h3>
          <div className="result-grid">
            <div className="result-row result-highlight">
              <span>Withholding per paycheck</span>
              <strong>{formatCurrency(parseDecimalString(mutation.data.withholding_amount))}</strong>
            </div>
            <div className="result-row">
              <span>Gross pay</span>
              <strong>{formatCurrency(parseDecimalString(mutation.data.gross_pay))}</strong>
            </div>
            <div className="result-row">
              <span>Annualized gross</span>
              <strong>{formatCurrency(parseDecimalString(mutation.data.annualized_gross))}</strong>
            </div>
            <div className="result-row">
              <span>Annualized withholding</span>
              <strong>{formatCurrency(parseDecimalString(mutation.data.annualized_withholding))}</strong>
            </div>
            <div className="result-row">
              <span>Effective rate</span>
              <strong>{(parseDecimalString(mutation.data.effective_rate) * 100).toFixed(2)}%</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

type W4Tab = "optimize" | "midyear" | "withholding";

export const W4Page = () => {
  const [tab, setTab] = useState<W4Tab>("optimize");

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">W-4 Optimization</h1>
      </div>

      <div className="tab-bar">
        <button
          type="button"
          className={`tab-btn${tab === "optimize" ? " active" : ""}`}
          onClick={() => setTab("optimize")}
        >
          W-4 Optimizer
        </button>
        <button
          type="button"
          className={`tab-btn${tab === "midyear" ? " active" : ""}`}
          onClick={() => setTab("midyear")}
        >
          Mid-Year Optimizer
        </button>
        <button
          type="button"
          className={`tab-btn${tab === "withholding" ? " active" : ""}`}
          onClick={() => setTab("withholding")}
        >
          Per-Paycheck Calculator
        </button>
      </div>

      {tab === "optimize" && <OptimizerTab />}
      {tab === "midyear" && <MidYearTab />}
      {tab === "withholding" && <WithholdingTab />}
    </div>
  );
};
