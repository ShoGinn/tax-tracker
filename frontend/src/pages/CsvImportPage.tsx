import { ModulePlaceholder } from "../components/ModulePlaceholder";

export const CsvImportPage = () => (
	<ModulePlaceholder
		title="CSV Import"
		description="Upload CSV files for paychecks, pensions, and non-taxable income with clear success/error summaries per row."
		endpointHints={[
			"POST /income/paychecks/import-csv",
			"POST /income/1099r/import-csv",
			"POST /income/non-taxable/import-csv",
		]}
	/>
);
