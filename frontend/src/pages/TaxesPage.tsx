import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { apiClient } from "../lib/api/client";
import type {
  FilingStatus,
  TaxCalculationRequest,
  TaxCalculationResponse,
  TaxReconciliationResponse,
} from "../lib/api/types";
import { FILING_STATUSES } from "../lib/constants";
import { useAppConfig } from "../lib/hooks";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();

// ---------------------------------------------------------------------------
// Shared result display
// ---------------------------------------------------------------------------

const TaxResultCard = ({ result }: { result: TaxCalculationResponse }) => {
  const [showBrackets, setShowBrackets] = useState(false);

  const totalFica = Object.values(result.fica_taxes).reduce(
    (s, v) => s + parseDecimalString(v as string),
    0,
  );

  return (
    <div className="card result-card">
      <h3 className="card-title">Result</h3>

      <div className="result-grid">
        <div className="result-row">
          <span>Gross income</span>
          <strong>{formatCurrency(parseDecimalString(result.gross_income))}</strong>
        </div>
        <div className="result-row">
          <span>{result.deduction_type} deduction</span>
          <strong>−{formatCurrency(parseDecimalString(result.deduction_amount))}</strong>
        </div>
        <div className="result-row">
          <span>Taxable income</span>
          <strong>{formatCurrency(parseDecimalString(result.taxable_income))}</strong>
        </div>
        <div className="result-row">
          <span>Federal tax (before credits)</span>
          <strong>{formatCurrency(parseDecimalString(result.federal_tax_owed))}</strong>
        </div>
        {parseDecimalString(result.child_tax_credits) > 0 && (
          <div className="result-row">
            <span>Child tax credits</span>
            <strong>−{formatCurrency(parseDecimalString(result.child_tax_credits))}</strong>
          </div>
        )}
        <div className="result-row result-divider">
          <span>Federal tax liability</span>
          <strong>{formatCurrency(parseDecimalString(result.total_tax_liability))}</strong>
        </div>
        <div className="result-row">
          <span>FICA taxes</span>
          <strong>{formatCurrency(totalFica)}</strong>
        </div>
        <div className="result-row result-highlight">
          <span>Effective rate</span>
          <strong>{(parseDecimalString(result.effective_tax_rate) * 100).toFixed(2)}%</strong>
        </div>
        <div className="result-row">
          <span>Marginal rate</span>
          <strong>{(parseDecimalString(result.marginal_tax_rate) * 100).toFixed(1)}%</strong>
        </div>
      </div>

      {result.notes.length > 0 && (
        <ul className="result-notes">
          {result.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      <button type="button" className="btn-ghost mt-2" onClick={() => setShowBrackets((v) => !v)}>
        {showBrackets ? "Hide" : "Show"} bracket breakdown
      </button>

      {showBrackets && (
        <div className="table-wrapper mt-2">
          <table className="data-table">
            <thead>
              <tr>
                <th>Bracket</th>
                <th className="num">Rate</th>
                <th className="num">Income in bracket</th>
                <th className="num">Tax in bracket</th>
              </tr>
            </thead>
            <tbody>
              {result.breakdown_by_bracket.map((b) => (
                <tr key={b.bracket}>
                  <td>{b.bracket}</td>
                  <td className="num">{(b.rate * 100).toFixed(0)}%</td>
                  <td className="num">{formatCurrency(b.taxable_income_in_bracket)}</td>
                  <td className="num">{formatCurrency(b.tax_in_bracket)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const ReconciliationCard = ({ result }: { result: TaxReconciliationResponse }) => {
  const isRefund = result.result_status === "REFUND";
  const isOwed = result.result_status === "OWED";
  const refundAmt = Math.abs(parseDecimalString(result.refund_or_owed));

  return (
    <>
      <TaxResultCard result={result} />

      <div
        className={`card reconciliation-card mt-2 ${isRefund ? "status-refund" : isOwed ? "status-owed" : "status-even"}`}
      >
        <h3 className="card-title">Withholding Reconciliation — {result.tax_year}</h3>

        <div className="result-grid">
          <div className="result-row">
            <span>Total federal withheld</span>
            <strong>{formatCurrency(parseDecimalString(result.total_federal_withheld))}</strong>
          </div>
          <div className="result-row">
            <span>FICA withheld</span>
            <strong>{formatCurrency(parseDecimalString(result.total_fica_withheld))}</strong>
          </div>
          <div className="result-row">
            <span>Total withheld</span>
            <strong>{formatCurrency(parseDecimalString(result.total_withheld))}</strong>
          </div>
          <div className="result-row">
            <span>Combined tax liability</span>
            <strong>{formatCurrency(parseDecimalString(result.combined_liability))}</strong>
          </div>
          <div
            className={`result-row result-highlight ${isRefund ? "text-refund" : isOwed ? "text-owed" : ""}`}
          >
            <span>{isRefund ? "Estimated refund" : isOwed ? "Amount owed" : "Break even"}</span>
            <strong>{isRefund || isOwed ? formatCurrency(refundAmt) : "—"}</strong>
          </div>
        </div>
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
// Direct calculator tab
// ---------------------------------------------------------------------------

const DirectCalcTab = () => {
  const { config, isLoading: configLoading } = useAppConfig();
  const didInitialSync = useRef(false);

  const [fields, setFields] = useState<TaxCalculationRequest>({
    w2_gross_income: "",
    pension_gross_income: "0",
    filing_status: config.filing_status,
    age_65_plus: config.age_65_plus,
    num_children: config.num_children,
    use_standard_deduction: config.use_standard_deduction,
    itemized_deduction_amount: config.itemized_deduction_amount,
    retirement_pretax_deductions: "0",
    non_taxable_income: "0",
    tax_year: currentYear,
  });

  // Sync profile fields from DB config once it loads (no-op if already cached at mount)
  useEffect(() => {
    if (!configLoading && !didInitialSync.current) {
      didInitialSync.current = true;
      setFields((prev) => ({
        ...prev,
        filing_status: config.filing_status,
        age_65_plus: config.age_65_plus,
        num_children: config.num_children,
        use_standard_deduction: config.use_standard_deduction,
        itemized_deduction_amount: config.itemized_deduction_amount,
      }));
    }
  }, [
    configLoading,
    config.filing_status,
    config.age_65_plus,
    config.num_children,
    config.use_standard_deduction,
    config.itemized_deduction_amount,
  ]);

  const mutation = useMutation({
    mutationFn: (data: TaxCalculationRequest) => apiClient.calculateTaxes(data),
  });

  const set = <K extends keyof TaxCalculationRequest>(key: K, val: TaxCalculationRequest[K]) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Direct Tax Calculator</h2>
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
            W-2 gross wages
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.w2_gross_income}
              onChange={(e) => set("w2_gross_income", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Pension / 1099-R gross
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.pension_gross_income}
              onChange={(e) => set("pension_gross_income", e.target.value)}
              placeholder="0.00"
            />
          </label>

          <label className="form-label">
            Retirement pre-tax deductions
            <input
              type="number"
              step="0.01"
              min="0"
              className="form-input"
              value={fields.retirement_pretax_deductions}
              onChange={(e) => set("retirement_pretax_deductions", e.target.value)}
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
              value={fields.non_taxable_income}
              onChange={(e) => set("non_taxable_income", e.target.value)}
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
              checked={fields.age_65_plus}
              onChange={(e) => set("age_65_plus", e.target.checked)}
            />
            Age 65+
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
              Itemized deduction amount
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.itemized_deduction_amount ?? ""}
                onChange={(e) => set("itemized_deduction_amount", e.target.value || null)}
                placeholder="0.00"
              />
            </label>
          )}
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Calculating…" : "Calculate taxes"}
        </button>
      </form>

      {mutation.data && <TaxResultCard result={mutation.data} />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Browser-record reconciliation tab
// ---------------------------------------------------------------------------

const FromDbTab = () => {
  const { config, isLoading: configLoading } = useAppConfig();
  const didInitialSync = useRef(false);
  const { data: yearsData } = useQuery({
    queryKey: ["available-tax-years"],
    queryFn: apiClient.getAvailableYears,
  });

  const [year, setYear] = useState(currentYear);
  const [filingStatus, setFilingStatus] = useState<FilingStatus>(config.filing_status);
  const [numChildren, setNumChildren] = useState(config.num_children);
  const [age65Plus, setAge65Plus] = useState(config.age_65_plus);
  const [useStandard, setUseStandard] = useState(config.use_standard_deduction);
  const [itemized, setItemized] = useState(Number(config.itemized_deduction_amount));

  useEffect(() => {
    if (!configLoading && !didInitialSync.current) {
      didInitialSync.current = true;
      setFilingStatus(config.filing_status);
      setNumChildren(config.num_children);
      setAge65Plus(config.age_65_plus);
      setUseStandard(config.use_standard_deduction);
      setItemized(Number(config.itemized_deduction_amount));
    }
  }, [
    configLoading,
    config.filing_status,
    config.num_children,
    config.age_65_plus,
    config.use_standard_deduction,
    config.itemized_deduction_amount,
  ]);

  const mutation = useMutation({
    mutationFn: () =>
      apiClient.calculateFromDb(year, {
        filing_status: filingStatus,
        num_children: numChildren,
        age_65_plus: age65Plus,
        use_standard_deduction: useStandard,
        itemized_deduction_amount: itemized,
      }),
  });

  const availableYears = yearsData?.available_years ?? [currentYear];

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Reconciliation from Database</h2>
      </div>

      <form
        className="card income-form mb-4"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <p className="helper-text">
          Aggregates all paychecks, 1099-R, and non-taxable income stored in this browser for the
          selected year and compares calculated tax liability against actual withholding.
        </p>

        <div className="form-grid">
          <label className="form-label">
            Tax year
            <select
              className="form-input"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {availableYears.map((y) => (
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
              value={filingStatus}
              onChange={(e) => setFilingStatus(e.target.value as FilingStatus)}
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
              value={numChildren}
              onChange={(e) => setNumChildren(Number(e.target.value))}
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
              checked={age65Plus}
              onChange={(e) => setAge65Plus(e.target.checked)}
            />
            Age 65+
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
              checked={useStandard}
              onChange={(e) => setUseStandard(e.target.checked)}
            />
            Use standard deduction
          </label>

          {!useStandard && (
            <label className="form-label">
              Itemized deduction amount
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={itemized}
                onChange={(e) => setItemized(Number(e.target.value))}
                placeholder="0.00"
              />
            </label>
          )}
        </div>

        {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

        <button type="submit" className="btn-primary mt-2" disabled={mutation.isPending}>
          {mutation.isPending ? "Calculating…" : "Run reconciliation"}
        </button>
      </form>

      {mutation.data && <ReconciliationCard result={mutation.data} />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

type TaxTab = "direct" | "from-db";

export const TaxesPage = () => {
  const [tab, setTab] = useState<TaxTab>("direct");

  return (
    <div className="page">
      <div className="tab-bar">
        <button
          type="button"
          className={`tab-btn${tab === "direct" ? " active" : ""}`}
          onClick={() => setTab("direct")}
        >
          Direct Calculator
        </button>
        <button
          type="button"
          className={`tab-btn${tab === "from-db" ? " active" : ""}`}
          onClick={() => setTab("from-db")}
        >
          Reconciliation from DB
        </button>
      </div>

      {tab === "direct" && <DirectCalcTab />}
      {tab === "from-db" && <FromDbTab />}
    </div>
  );
};
