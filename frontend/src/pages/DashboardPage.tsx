import { useQuery } from "@tanstack/react-query";

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
				(total, paycheck) => total + parseDecimalString(paycheck.gross_wages),
				0,
			);
			const federalWithholding =
				paychecks.reduce(
					(total, paycheck) =>
						total + parseDecimalString(paycheck.federal_withholding),
					0,
				) +
				pensions.reduce(
					(total, pension) =>
						total + parseDecimalString(pension.federal_withholding),
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

	if (summaryQuery.isLoading) {
		return (
			<p className="status-message">Loading dashboard for {selectedYear}...</p>
		);
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

	if (!summary) {
		return <p className="status-message">No data available yet.</p>;
	}

	return (
		<section className="dashboard-grid">
			<article className="metric-card feature">
				<p className="metric-label">Household Cashflow ({summary.year})</p>
				<p className="metric-value">
					{formatCurrency(summary.totals.householdCashflow)}
				</p>
				<p className="metric-caption">
					W-2 + 1099-R + non-taxable income tracked this year
				</p>
			</article>

			<article className="metric-card">
				<p className="metric-label">Federal Withholding</p>
				<p className="metric-value">
					{formatCurrency(summary.totals.federalWithholding)}
				</p>
			</article>

			<article className="metric-card">
				<p className="metric-label">W-2 Gross</p>
				<p className="metric-value">{formatCurrency(summary.totals.w2Gross)}</p>
			</article>

			<article className="metric-card">
				<p className="metric-label">1099-R Gross</p>
				<p className="metric-value">
					{formatCurrency(summary.totals.pensionGross)}
				</p>
			</article>

			<article className="metric-card">
				<p className="metric-label">Non-taxable Income</p>
				<p className="metric-value">
					{formatCurrency(summary.totals.nonTaxableGross)}
				</p>
			</article>

			<article className="metric-card compact">
				<p className="metric-label">Records Loaded</p>
				<p className="metric-caption">
					{summary.counts.paychecks} paychecks • {summary.counts.pensions}{" "}
					pensions • {summary.counts.nonTaxable} non-taxable entries
				</p>
			</article>
		</section>
	);
};
