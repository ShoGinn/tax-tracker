import { ModulePlaceholder } from "../components/ModulePlaceholder";

export const TaxesPage = () => (
	<ModulePlaceholder
		title="Federal Tax Calculator"
		description="Run direct tax scenarios and compare tax liability against actual withholding from database entries."
		endpointHints={[
			"POST /taxes/calculate",
			"POST /taxes/calculate-from-db/{year}",
			"GET /taxes/brackets/{year}",
			"GET /taxes/fica/{year}",
		]}
	/>
);
