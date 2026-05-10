import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../lib/api/client";
import type { FilingStatus, W4OptimizeRequest, W4OptimizeResponse, WithholdingCalcRequest } from "../lib/api/types";
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
        <span>Estimated tax liability</span>
        <strong>{formatCurrency(parseDecimalString(result.estimated_tax_liability))}</strong>
      </div>
      <div className="result-row">
        <span>Target withholding</span>
        <strong>{formatCurrency(parseDecimalString(result.target_total_withholding))}</strong>
      </div>
      <div className="result-row result-divider">
        <span>Adjustment needed</span>
        <strong className={parseDecimalString(result.adjustment_needed) < 0 ? "text-owed" : "text-refund"}>
          {formatCurrency(Math.abs(parseDecimalString(result.adjustment_needed)))}
          {parseDecimalString(result.adjustment_needed) < 0 ? " more/yr" : " less/yr"}
        </strong>
      </div>
    </div>

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
            <span className="w4-step-label">Step 4a — Other income</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step4a_other_income))}</span>
            {rec.step4a_explanation && <p className="w4-step-note">{rec.step4a_explanation}</p>}
          </div>

          <div className="w4-step">
            <span className="w4-step-label">Step 4b — Deductions</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step4b_deductions))}</span>
            {rec.step4b_explanation && <p className="w4-step-note">{rec.step4b_explanation}</p>}
          </div>

          <div className="w4-step result-highlight">
            <span className="w4-step-label">Step 4c — Extra per paycheck</span>
            <span className="w4-step-value">{formatCurrency(parseDecimalString(rec.step4c_extra_withholding))}</span>
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

type W4Tab = "optimize" | "withholding";

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
          className={`tab-btn${tab === "withholding" ? " active" : ""}`}
          onClick={() => setTab("withholding")}
        >
          Per-Paycheck Calculator
        </button>
      </div>

      {tab === "optimize" && <OptimizerTab />}
      {tab === "withholding" && <WithholdingTab />}
    </div>
  );
};
