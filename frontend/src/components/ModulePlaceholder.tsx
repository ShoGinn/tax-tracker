interface ModulePlaceholderProps {
	title: string;
	description: string;
	endpointHints: string[];
}

export const ModulePlaceholder = ({
	title,
	description,
	endpointHints,
}: ModulePlaceholderProps) => {
	return (
		<section className="module-card">
			<h2>{title}</h2>
			<p>{description}</p>
			<h3>Planned API wiring</h3>
			<ul>
				{endpointHints.map((hint) => (
					<li key={hint}>{hint}</li>
				))}
			</ul>
		</section>
	);
};
