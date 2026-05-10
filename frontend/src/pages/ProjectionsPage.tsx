import { ModulePlaceholder } from "../components/ModulePlaceholder";

export const ProjectionsPage = () => (
	<ModulePlaceholder
		title="Tax Projections"
		description="Model next-year tax outcomes and compare year-over-year deltas using direct inputs or historical database averages."
		endpointHints={[
			"POST /projections/project-year",
			"POST /projections/compare-years",
			"POST /projections/from-database",
		]}
	/>
);
