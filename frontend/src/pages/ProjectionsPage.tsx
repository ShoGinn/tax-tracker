import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../lib/api/client";
import type { CompareYearsRequest, FilingStatus, ProjectYearRequest, ProjectYearResponse } from "../lib/api/types";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();

const FILING_STATUSES: { value: FilingStatus; label: string }[] = [
  { value: "single", label: "Single" },
  { value: "married_filing_jointly", label: "Married Filing Jointly" },
  { value: "married_filing_separately", label: "Married Filing Separately" },
  { value: "head_of_household", label: "Head of Household" },
];

const YEARS = Array.from({ length: 4 }, (_, i) => currentYear - i + 1);

// ---------------------------------------------------------------------------
// Shared projection result card
// ---------------------------------------------------------------------------

const ProjectionCard = ({ result, label }: { result: ProjectYearResponse; label?: string }) => (
  <div className="card result-card">
    <h3 className="card-title">{label ?? `${result.year} Projection`}</h3>
    <div className="result-grid">
      <div className="result-row">
        <span>W-2 gross</span>
        <span>{formatCurrency(parseDecimalString(result.w2_gross))}</span>
      </div>
      <div className="result-row">
        <span>W-2 taxable wages</span>
        <span>{formatCurrency(parseDecimalString(result.w2_taxable))}</span>
      </div>
      <div className="result-row">
        <span>Pension taxable</span>
        <span>{formatCurrency(parseDecimalString(result.pension_taxable))}</span>
      </div>
      <div className="result-row result-divider">
        <span>Taxable income (after deduction)</span>
        <span>{formatCurrency(parseDecimalString(result.taxable_income))}</span>
      </div>
      <div className="result-row">
        <span>Federal income tax</span>
        <span>{formatCurrency(parseDecimalString(result.federal_tax_liability))}</span>
      </div>
      <div className="result-row">
        <span>FICA liability</span>
        <span>{formatCurrency(parseDecimalString(result.fica_liability))}</span>
      </div>
      <div className="result-row result-highlight">
        <span>Total tax liability</span>
        <strong>{formatCurrency(parseDecimalString(result.total_tax_liability))}</strong>
      </div>
      <div className="result-row">
        <span>Effective rate</span>
        <span>{(parseDecimalString(result.effective_rate) * 100).toFixed(2)}%</span>
      </div>
      <div className="result-row">
        <span>Marginal rate</span>
        <span>{(parseDecimalString(result.marginal_rate) * 100).toFixed(0)}%</span>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Single-year projection tab
// ---------------------------------------------------------------------------

const ProjectYearTab = () => {
  const [fields, setFields] = useState<ProjectYearRequest>({
    projection_year: currentYear + 1,
    filing_status: "single",
    num_children: 0,
    w2_gross: "",
    w2_pretax_deductions: "0",
    pension_gross: "0",
    pension_pretax_deductions: "0",
    va_disability: "0",
    use_standard_deduction: true,
    itemized_deduction_amount: "0",
  });

  const mutation = useMutation({
    mutationFn: (data: ProjectYearRequest) => apiClient.projectYear(data),
  });

  const set = <K extends keyof ProjectYearRequest>(key: K, val: ProjectYearRequest[K]) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Single-Year Projection</h2>
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
            Projection year
            <select
              className="form-input"
              value={fields.projection_year}
              onChange={(e) => set("projection_year", Number(e.target.value))}
            >
              {YEARS.map((y) => (
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
            Expected W-2 gross wages
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.w2_gross}
              onChange={(e) => set("w2_gross", e.target.value)}
              required
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            W-2 pre-tax deductions (401k, HSA, etc.)
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.w2_pretax_deductions}
              onChange={(e) => set("w2_pretax_deductions", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Expected pension gross (1099-R)
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.pension_gross}
              onChange={(e) => set("pension_gross", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Pension pre-tax deductions (SBP, insurance)
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.pension_pretax_deductions}
              onChange={(e) => set("pension_pretax_deductions", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Non-taxable income
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.va_disability}
              onChange={(e) => set("va_disability", e.target.value)}
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
              checked={fields.use_standard_deduction}
              onChange={(e) => set("use_standard_deduction", e.target.checked)}
            />
            Use standard deduction
          </label>

          {!fields.use_standard_deduction && (
            <label className="form-label">
              Itemized deductions total
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.itemized_deduction_amount}
                onChange={(e) => set("itemized_deduction_amount", e.target.value)}
                placeholder="0.00"
              />
            </label>
          )}
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Projecting…" : "Project taxes"}
        </button>
      </form>

      {mutation.data && <ProjectionCard result={mutation.data} />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Year comparison tab
// ---------------------------------------------------------------------------

const CompareYearsTab = () => {
  const [fields, setFields] = useState<CompareYearsRequest>({
    base_year: currentYear,
    comparison_year: currentYear + 1,
    filing_status: "single",
    num_children: 0,
    base_w2_gross: "",
    comparison_w2_gross: "",
    base_pension: "0",
    comparison_pension: "0",
  });

  const mutation = useMutation({
    mutationFn: (data: CompareYearsRequest) => apiClient.compareYears(data),
  });

  const set = <K extends keyof CompareYearsRequest>(key: K, val: CompareYearsRequest[K]) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Year-over-Year Comparison</h2>
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
            Base year
            <select
              className="form-input"
              value={fields.base_year}
              onChange={(e) => set("base_year", Number(e.target.value))}
            >
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Base year W-2 gross
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.base_w2_gross}
              onChange={(e) => set("base_w2_gross", e.target.value)}
              required
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Base year pension gross
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.base_pension}
              onChange={(e) => set("base_pension", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Comparison year
            <select
              className="form-input"
              value={fields.comparison_year}
              onChange={(e) => set("comparison_year", Number(e.target.value))}
            >
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Comparison year W-2 gross
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.comparison_w2_gross}
              onChange={(e) => set("comparison_w2_gross", e.target.value)}
              required
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Comparison year pension gross
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.comparison_pension}
              onChange={(e) => set("comparison_pension", e.target.value)}
              placeholder="0.00"
            />
          </label>
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Comparing…" : "Compare years"}
        </button>
      </form>

      {mutation.data && (
        <>
          <div className="projections-grid">
            {mutation.data.projections.map((proj) => (
              <ProjectionCard key={proj.year} result={proj} />
            ))}
          </div>

          {mutation.data.comparisons.map((cmp) => (
            <div key={`${cmp.from_year}-${cmp.to_year}`} className="card result-card mt-2">
              <h3 className="card-title">
                {cmp.from_year} → {cmp.to_year} Changes
              </h3>
              <div className="result-grid">
                <div className="result-row">
                  <span>Taxable income change</span>
                  <span className={cmp.income_change.amount >= 0 ? "text-owed" : "text-refund"}>
                    {cmp.income_change.amount >= 0 ? "+" : ""}
                    {formatCurrency(cmp.income_change.amount)} ({cmp.income_change.percentage.toFixed(1)}%)
                  </span>
                </div>
                <div className="result-row">
                  <span>Tax liability change</span>
                  <span className={cmp.tax_change.amount >= 0 ? "text-owed" : "text-refund"}>
                    {cmp.tax_change.amount >= 0 ? "+" : ""}
                    {formatCurrency(cmp.tax_change.amount)} ({cmp.tax_change.percentage.toFixed(1)}%)
                  </span>
                </div>
                <div className="result-row">
                  <span>Effective rate</span>
                  <span>
                    {(cmp.effective_rate_change.from * 100).toFixed(2)}% →{" "}
                    {(cmp.effective_rate_change.to * 100).toFixed(2)}%
                  </span>
                </div>
                {cmp.marginal_bracket_change.moved_bracket && (
                  <div className="result-row result-highlight">
                    <span>Moved to new tax bracket</span>
                    <span>
                      {(cmp.marginal_bracket_change.from * 100).toFixed(0)}% →{" "}
                      {(cmp.marginal_bracket_change.to * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

type ProjectionsTab = "project" | "compare";

export const ProjectionsPage = () => {
  const [tab, setTab] = useState<ProjectionsTab>("project");

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Tax Projections</h1>
      </div>

      <div className="tab-bar">
        <button
          type="button"
          className={`tab-btn${tab === "project" ? " active" : ""}`}
          onClick={() => setTab("project")}
        >
          Single Year
        </button>
        <button
          type="button"
          className={`tab-btn${tab === "compare" ? " active" : ""}`}
          onClick={() => setTab("compare")}
        >
          Year Comparison
        </button>
      </div>

      {tab === "project" && <ProjectYearTab />}
      {tab === "compare" && <CompareYearsTab />}
    </div>
  );
};
