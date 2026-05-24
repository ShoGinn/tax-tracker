import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../lib/api/client";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1; // 1–12

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export const DashboardPage = () => {
  const { data: yearsData } = useQuery({
    queryKey: ["available-tax-years"],
    queryFn: apiClient.getAvailableYears,
  });

  const selectedYear = yearsData?.latest_year ?? currentYear;

  const configQuery = useQuery({
    queryKey: ["app-config"],
    queryFn: apiClient.getConfig,
  });

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary", selectedYear],
    queryFn: async () => {
      const [paychecks, pensions, nonTaxableIncome] = await Promise.all([
        apiClient.listPaychecks(selectedYear),
        apiClient.listPensions(selectedYear),
        apiClient.listNonTaxableIncome(selectedYear),
      ]);

      const w2Gross = paychecks.reduce((total, p) => total + parseDecimalString(p.gross_wages), 0);
      const w2PretaxDeductions = paychecks.reduce(
        (total, p) => total + parseDecimalString(p.total_pretax_deductions),
        0,
      );
      const federalWithholding =
        paychecks.reduce((total, p) => total + parseDecimalString(p.federal_withholding), 0) +
        pensions.reduce((total, p) => total + parseDecimalString(p.federal_withholding), 0);
      const pensionGross = pensions.reduce((total, p) => total + parseDecimalString(p.gross_amount), 0);
      const pensionPretaxDeductions = pensions.reduce((total, p) => total + parseDecimalString(p.pretax_deductions), 0);
      const nonTaxableGross = nonTaxableIncome.reduce((total, e) => total + parseDecimalString(e.amount), 0);

      return {
        year: selectedYear,
        counts: { paychecks: paychecks.length, pensions: pensions.length, nonTaxable: nonTaxableIncome.length },
        totals: {
          w2Gross,
          w2PretaxDeductions,
          pensionGross,
          pensionPretaxDeductions,
          nonTaxableGross,
          federalWithholding,
          householdCashflow: w2Gross + pensionGross + nonTaxableGross,
        },
      };
    },
  });

  const isCurrentYear = selectedYear === currentYear;
  // Annualize only for the current calendar year
  const annFactor = isCurrentYear && currentMonth > 0 ? 12 / currentMonth : 1;
  const ann = (v: number) => Math.round(v * annFactor * 100) / 100;

  const predictionQuery = useQuery({
    queryKey: ["dashboard-prediction", selectedYear, configQuery.data, summaryQuery.data],
    enabled: !!configQuery.data && !!summaryQuery.data,
    queryFn: async () => {
      const config = configQuery.data!;
      const { totals } = summaryQuery.data!;
      return apiClient.projectYear({
        projection_year: selectedYear,
        filing_status: config.filing_status,
        num_children: config.num_children,
        w2_gross: String(ann(totals.w2Gross)),
        w2_pretax_deductions: String(ann(totals.w2PretaxDeductions)),
        pension_gross: String(ann(totals.pensionGross)),
        pension_pretax_deductions: String(ann(totals.pensionPretaxDeductions)),
        va_disability: String(ann(totals.nonTaxableGross)),
        use_standard_deduction: config.use_standard_deduction,
        itemized_deduction_amount: config.itemized_deduction_amount,
      });
    },
  });

  if (summaryQuery.isLoading || configQuery.isLoading) {
    return <p className="status-message">Loading dashboard for {selectedYear}...</p>;
  }

  if (summaryQuery.isError) {
    return (
      <p className="status-message error">
        {summaryQuery.error instanceof Error ? summaryQuery.error.message : "Unable to load dashboard"}
      </p>
    );
  }

  const summary = summaryQuery.data;
  if (!summary) return <p className="status-message">No data available yet.</p>;

  const prediction = predictionQuery.data;

  const projW2Gross = ann(summary.totals.w2Gross);
  const projPensionGross = ann(summary.totals.pensionGross);
  const projNonTaxable = ann(summary.totals.nonTaxableGross);
  const projHouseholdCashflow = projW2Gross + projPensionGross + projNonTaxable;
  const projWithholding = ann(summary.totals.federalWithholding);
  const projTotalTax = prediction ? parseDecimalString(prediction.total_tax_liability) : null;
  const projNetTakeHome = projTotalTax !== null ? projHouseholdCashflow - projTotalTax : null;

  const annNote = isCurrentYear
    ? `Projected from Jan–${MONTH_NAMES[currentMonth - 1]} data × ${(12 / currentMonth).toFixed(2)}`
    : `Full year ${selectedYear}`;

  return (
    <section className="dashboard-grid">
      {/* ── YTD actuals ── */}
      <article className="metric-card feature">
        <p className="metric-label">Household Cashflow ({summary.year})</p>
        <p className="metric-value">{formatCurrency(summary.totals.householdCashflow)}</p>
        <p className="metric-caption">W-2 + 1099-R + non-taxable income tracked this year</p>
      </article>

      <article className="metric-card">
        <p className="metric-label">Federal Withholding</p>
        <p className="metric-value">{formatCurrency(summary.totals.federalWithholding)}</p>
      </article>

      <article className="metric-card">
        <p className="metric-label">W-2 Gross</p>
        <p className="metric-value">{formatCurrency(summary.totals.w2Gross)}</p>
      </article>

      <article className="metric-card">
        <p className="metric-label">1099-R Gross</p>
        <p className="metric-value">{formatCurrency(summary.totals.pensionGross)}</p>
      </article>

      <article className="metric-card">
        <p className="metric-label">Non-taxable Income</p>
        <p className="metric-value">{formatCurrency(summary.totals.nonTaxableGross)}</p>
      </article>

      <article className="metric-card compact">
        <p className="metric-label">Records Loaded</p>
        <p className="metric-caption">
          {summary.counts.paychecks} paychecks • {summary.counts.pensions} pensions • {summary.counts.nonTaxable}{" "}
          non-taxable entries
        </p>
      </article>

      {/* ── Full-year predictions (mirrors the cashflow cards above) ── */}
      {predictionQuery.isLoading && (
        <article className="metric-card">
          <p className="metric-caption">Calculating full-year prediction…</p>
        </article>
      )}

      {predictionQuery.isError && (
        <article className="metric-card">
          <p className="metric-caption error">
            Prediction unavailable:{" "}
            {predictionQuery.error instanceof Error ? predictionQuery.error.message : "Unknown error"}
          </p>
        </article>
      )}

      {prediction && (
        <>
          <article className="metric-card feature prediction-feature">
            <p className="metric-label">Projected Household Cashflow ({selectedYear})</p>
            <p className="metric-value">{formatCurrency(projHouseholdCashflow)}</p>
            <p className="metric-caption">{annNote}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Federal Withholding</p>
            <p className="metric-value">{formatCurrency(projWithholding)}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected W-2 Gross</p>
            <p className="metric-value">{formatCurrency(projW2Gross)}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected 1099-R Gross</p>
            <p className="metric-value">{formatCurrency(projPensionGross)}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Non-taxable Income</p>
            <p className="metric-value">{formatCurrency(projNonTaxable)}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Total Tax Liability</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(prediction.total_tax_liability))}</p>
            <p className="metric-caption">
              {parseDecimalString(prediction.effective_rate).toFixed(1)}% effective •{" "}
              {parseDecimalString(prediction.marginal_rate).toFixed(0)}% marginal
            </p>
          </article>

          {projNetTakeHome !== null && (
            <article className="metric-card">
              <p className="metric-label">Projected Net Take-home</p>
              <p className="metric-value">{formatCurrency(projNetTakeHome)}</p>
              <p className="metric-caption">Cashflow minus total tax liability</p>
            </article>
          )}
        </>
      )}
    </section>
  );
};
