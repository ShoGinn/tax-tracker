import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { apiClient } from "../lib/api/client";
import { formatCurrency, parseDecimalString } from "../lib/money";

const currentYear = new Date().getFullYear();

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
        (total, paycheck) =>
          total + parseDecimalString(paycheck.gross_wages) + parseDecimalString(paycheck.bonus),
        0,
      );
      const federalWithholding =
        paychecks.reduce(
          (total, paycheck) => total + parseDecimalString(paycheck.federal_withholding),
          0,
        ) +
        pensions.reduce(
          (total, pension) => total + parseDecimalString(pension.federal_withholding),
          0,
        );
      const pensionGross = pensions.reduce(
        (total, pension) => total + parseDecimalString(pension.gross_amount),
        0,
      );
      const nonTaxableGross = nonTaxableIncome.reduce(
        (total, entry) => total + parseDecimalString(entry.amount),
        0,
      );

      return {
        year: selectedYear,
        counts: {
          paychecks: paychecks.length,
          pensions: pensions.length,
          nonTaxable: nonTaxableIncome.length,
        },
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
    return <p className="status-message">Preparing your {selectedYear} plan…</p>;
  }

  if (summaryQuery.isError) {
    return (
      <p className="status-message error">
        {summaryQuery.error instanceof Error
          ? summaryQuery.error.message
          : "Unable to load dashboard"}
      </p>
    );
  }

  const summary = summaryQuery.data;
  if (!summary) return <p className="status-message">No data available yet.</p>;

  const projection = projectionQuery.data;
  const projectedIncome = projection
    ? parseDecimalString(projection.projected.w2_gross) +
      parseDecimalString(projection.projected.pension_gross) +
      parseDecimalString(projection.projected.va_income)
    : 0;
  const projectedBalance = projection ? parseDecimalString(projection.projected.refund_or_owed) : 0;
  const hasRecords =
    summary.counts.paychecks + summary.counts.pensions + summary.counts.nonTaxable > 0;
  const balanceLabel =
    projectedBalance > 0
      ? "Projected refund"
      : projectedBalance < 0
        ? "Projected amount due"
        : "Projected balance";
  const balanceTone =
    projectedBalance > 0
      ? "plan-status--positive"
      : projectedBalance < 0
        ? "plan-status--attention"
        : "plan-status--neutral";

  return (
    <div className="dashboard-page">
      <section className={`plan-status ${balanceTone}`} aria-labelledby="plan-status-heading">
        <div className="plan-status-copy">
          <div className="status-kicker-row">
            <span className="status-kicker">{selectedYear} outlook</span>
            <span className="live-badge">
              <span aria-hidden="true" /> Updated from your records
            </span>
          </div>
          <h2 id="plan-status-heading" className="plan-status-label">
            {projection ? balanceLabel : "Plan snapshot"}
          </h2>
          <p className="plan-status-value">
            {projection ? formatCurrency(Math.abs(projectedBalance)) : "Add income to get started"}
          </p>
          <p className="plan-status-detail">
            {projection
              ? `${parseDecimalString(projection.projected.effective_rate).toFixed(1)}% effective federal rate · ${parseDecimalString(projection.projected.marginal_rate).toFixed(0)}% marginal rate · ${formatCurrency(parseDecimalString(projection.projected.total_withheld))} projected withholding`
              : "Once records are available, we’ll estimate your full-year income, liability, and withholding balance."}
          </p>
        </div>
        <div className="plan-status-action">
          <span>Next best step</span>
          <strong>{hasRecords ? "Review your W-4 plan" : "Add your first income record"}</strong>
          <Link to={hasRecords ? "/w4" : "/income"}>
            {hasRecords ? "Open withholding plan" : "Add income"} <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      <section className="dashboard-section" aria-labelledby="snapshot-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Recorded so far</p>
            <h2 id="snapshot-heading">Year-to-date snapshot</h2>
          </div>
          <Link to="/income">Manage income →</Link>
        </div>
        <div className="metric-grid">
          <article className="metric-card metric-card--primary">
            <p className="metric-label">Household Cashflow</p>
            <p className="metric-value">{formatCurrency(summary.totals.householdCashflow)}</p>
            <p className="metric-caption">Taxable and non-taxable income recorded</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">Federal Withholding</p>
            <p className="metric-value">{formatCurrency(summary.totals.federalWithholding)}</p>
            <p className="metric-caption">W-2 and pension withholding</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">W-2 Gross</p>
            <p className="metric-value">{formatCurrency(summary.totals.w2Gross)}</p>
            <p className="metric-caption">Across {summary.counts.paychecks} paychecks</p>
          </article>
          <article className="metric-card">
            <p className="metric-label">Retirement income</p>
            <p className="metric-value">{formatCurrency(summary.totals.pensionGross)}</p>
            <p className="metric-caption">Across {summary.counts.pensions} 1099-R records</p>
          </article>
        </div>
      </section>

      <div className="dashboard-lower-grid">
        <section
          className="dashboard-section projection-panel"
          aria-labelledby="projection-heading"
        >
          <div className="section-heading">
            <div>
              <p className="section-kicker">Looking ahead</p>
              <h2 id="projection-heading">Full-year projection</h2>
            </div>
            <Link to="/projections">Explore scenarios →</Link>
          </div>
          {projectionQuery.isLoading && <p className="loading-text">Calculating projection…</p>}
          {projectionQuery.isError && (
            <p className="error-text">Projection unavailable: {projectionQuery.error.message}</p>
          )}
          {projection && (
            <div className="projection-list">
              <div>
                <span>Projected household income</span>
                <strong>{formatCurrency(projectedIncome)}</strong>
              </div>
              <div>
                <span>Total federal tax liability</span>
                <strong>
                  {formatCurrency(parseDecimalString(projection.projected.total_tax_liability))}
                </strong>
              </div>
              <div>
                <span>Projected net after tax</span>
                <strong>
                  {formatCurrency(
                    projectedIncome - parseDecimalString(projection.projected.total_tax_liability),
                  )}
                </strong>
              </div>
              <p>
                {projection.is_current_year
                  ? `Based on records through ${projection.as_of_date} and remaining pay periods.`
                  : `Based on the complete ${selectedYear} tax year.`}
              </p>
            </div>
          )}
        </section>

        <section className="dashboard-section workflow-panel" aria-labelledby="workflow-heading">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Planning path</p>
              <h2 id="workflow-heading">Keep your plan current</h2>
            </div>
          </div>
          <ol className="workflow-list">
            <li>
              <span>1</span>
              <div>
                <strong>Confirm your profile</strong>
                <p>Filing status, dependents, and deduction choices</p>
              </div>
              <Link to="/settings" aria-label="Confirm your tax profile">
                →
              </Link>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Keep income current</strong>
                <p>{hasRecords ? "Records are available for this year" : "No records added yet"}</p>
              </div>
              <Link to="/income" aria-label="Manage income records">
                →
              </Link>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Act on your outlook</strong>
                <p>Review liability, then tune withholding if needed</p>
              </div>
              <Link to="/taxes" aria-label="Review tax position">
                →
              </Link>
            </li>
          </ol>
        </section>
      </div>
    </div>
  );
};
