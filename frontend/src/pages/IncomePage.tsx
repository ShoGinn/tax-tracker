import { ModulePlaceholder } from "../components/ModulePlaceholder";

export const IncomePage = () => (
	<ModulePlaceholder
		title="Income Workspace"
		description="Create, review, and delete paycheck, 1099-R, and non-taxable income records with year filters and computed totals."
		endpointHints={[
			"GET /income/paychecks?year=YYYY",
			"POST /income/paychecks",
			"DELETE /income/paychecks/{id}",
			"GET /income/1099r?year=YYYY",
			"POST /income/1099r",
			"GET /income/non-taxable?year=YYYY",
			"POST /income/non-taxable",
		]}
	/>
);
