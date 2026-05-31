import { useQuery } from "@tanstack/react-query";

import { apiClient } from "../lib/api/client";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export const DashboardPage = () => {
  const { data: yearsData } = useQuery({
    queryKey: ["available-tax-years"],
    queryFn: apiClient.getAvailableYears,
  });

  const selectedYear = yearsData?.latest_year ?? currentYear;

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary", selectedYear],
    queryFn: async () => {
      const [paychecks, pensions, nonTaxableIncome] = await Promise.all([
        apiClient.listPaychecks(selectedYear),
        apiClient.listPensions(selectedYear),
        apiClient.listNonTaxableIncome(selectedYear),
      ]);

      const w2Gross = paychecks.reduce(
        (total, p) => total + parseDecimalString(p.gross_wages) + parseDecimalString(p.bonus),
        0,
      );
      const federalWithholding =
        paychecks.reduce((total, p) => total + parseDecimalString(p.federal_withholding), 0) +
        pensions.reduce((total, p) => total + parseDecimalString(p.federal_withholding), 0);
      const pensionGross = pensions.reduce((total, p) => total + parseDecimalString(p.gross_amount), 0);
      const nonTaxableGross = nonTaxableIncome.reduce((total, e) => total + parseDecimalString(e.amount), 0);

      return {
        year: selectedYear,
        counts: { paychecks: paychecks.length, pensions: pensions.length, nonTaxable: nonTaxableIncome.length },
        totals: {
          w2Gross,
          pensionGross,
          nonTaxableGross,
          federalWithholding,
          householdCashflow: w2Gross + pensionGross + nonTaxableGross,
        },
      };
    },
  });

  const projectionQuery = useQuery({
    queryKey: ["dashboard-projection", selectedYear],
    queryFn: () => apiClient.getDashboardProjection(selectedYear),
  });

  if (summaryQuery.isLoading) {
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

  const proj = projectionQuery.data;
  const projNote = proj?.is_current_year
    ? `Projected from YTD + remaining pay periods (as of ${proj.as_of_date})`
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

      {/* ── Full-year projections from backend ── */}
      {projectionQuery.isLoading && (
        <article className="metric-card">
          <p className="metric-caption">Calculating full-year projection…</p>
        </article>
      )}

      {projectionQuery.isError && (
        <article className="metric-card">
          <p className="metric-caption error">
            Projection unavailable:{" "}
            {projectionQuery.error instanceof Error ? projectionQuery.error.message : "Unknown error"}
          </p>
        </article>
      )}

      {proj && (
        <>
          <article className="metric-card feature prediction-feature">
            <p className="metric-label">Projected Household Cashflow ({selectedYear})</p>
            <p className="metric-value">
              {formatCurrency(
                parseDecimalString(proj.projected.w2_gross) +
                  parseDecimalString(proj.projected.pension_gross) +
                  parseDecimalString(proj.projected.va_income),
              )}
            </p>
            <p className="metric-caption">{projNote}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Federal Withholding</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(proj.projected.total_withheld))}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected W-2 Gross</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(proj.projected.w2_gross))}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected 1099-R Gross</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(proj.projected.pension_gross))}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Non-taxable Income</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(proj.projected.va_income))}</p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Total Tax Liability</p>
            <p className="metric-value">{formatCurrency(parseDecimalString(proj.projected.total_tax_liability))}</p>
            <p className="metric-caption">
              {parseDecimalString(proj.projected.effective_rate).toFixed(1)}% effective •{" "}
              {parseDecimalString(proj.projected.marginal_rate).toFixed(0)}% marginal
            </p>
          </article>

          <article className="metric-card">
            <p className="metric-label">Projected Net Take-home</p>
            <p className="metric-value">
              {formatCurrency(
                parseDecimalString(proj.projected.w2_gross) +
                  parseDecimalString(proj.projected.pension_gross) +
                  parseDecimalString(proj.projected.va_income) -
                  parseDecimalString(proj.projected.total_tax_liability),
              )}
            </p>
            <p className="metric-caption">Cashflow minus total tax liability</p>
          </article>
        </>
      )}
    </section>
  );
};
