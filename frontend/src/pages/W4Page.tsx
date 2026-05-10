import { ModulePlaceholder } from "../components/ModulePlaceholder";

export const W4Page = () => (
	<ModulePlaceholder
		title="W-4 Optimizer"
		description="Optimize W-4 settings for annual or mid-year updates and estimate paycheck-level withholding."
		endpointHints={[
			"POST /w4/optimize",
			"POST /w4/optimize-midyear-from-db",
			"POST /w4/calculate-withholding",
			"POST /w4/estimate-annual-withholding",
		]}
	/>
);
