import { NavLink, Outlet } from "react-router-dom";

const navigation = [
	{ to: "/", label: "Dashboard" },
	{ to: "/income", label: "Income" },
	{ to: "/taxes", label: "Taxes" },
	{ to: "/w4", label: "W-4" },
	{ to: "/projections", label: "Projections" },
	{ to: "/imports", label: "CSV Import" },
	{ to: "/auth", label: "Auth" },
];

export const AppShell = () => {
	return (
		<div className="app-shell">
			<aside className="sidebar">
				<p className="brand-kicker">Tax Tracker</p>
				<h1>Federal Planning Studio</h1>
				<p className="brand-copy">
					From paychecks to W-4 moves, one command center for your federal
					planning.
				</p>
				<nav aria-label="Main navigation">
					<ul>
						{navigation.map((item) => (
							<li key={item.to}>
								<NavLink
									to={item.to}
									end={item.to === "/"}
									className={({ isActive }) =>
										isActive ? "nav-link active" : "nav-link"
									}
								>
									{item.label}
								</NavLink>
							</li>
						))}
					</ul>
				</nav>
			</aside>

			<main className="content-area">
				<header className="content-header">
					<p>v1 Frontend Foundation</p>
					<span>Backend: FastAPI</span>
				</header>
				<Outlet />
			</main>
		</div>
	);
};
