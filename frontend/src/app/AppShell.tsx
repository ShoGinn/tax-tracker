import { Link, NavLink, Outlet, useLocation } from "react-router";

const planNavigation = [
  { to: "/", label: "Overview", marker: "01" },
  { to: "/income", label: "Income", marker: "02" },
  { to: "/taxes", label: "Tax position", marker: "03" },
  { to: "/w4", label: "W-4 plan", marker: "04" },
  { to: "/projections", label: "Projections", marker: "05" },
];

const manageNavigation = [
  { to: "/imports", label: "Import data", marker: "↗" },
  { to: "/settings", label: "Profile & backup", marker: "•" },
];

const githubUrl = "https://github.com/ShoGinn/tax-tracker";

const pageMeta: Record<string, { eyebrow: string; title: string; description: string }> = {
  "/": {
    eyebrow: "Plan overview",
    title: "Your federal tax plan",
    description: "Track where you are today and what your full year is shaping up to look like.",
  },
  "/income": {
    eyebrow: "Step 2 of 5",
    title: "Income records",
    description: "Keep paychecks, retirement income, and non-taxable cash flow current.",
  },
  "/taxes": {
    eyebrow: "Step 3 of 5",
    title: "Tax position",
    description: "Estimate federal liability and reconcile it against what you have withheld.",
  },
  "/w4": {
    eyebrow: "Step 4 of 5",
    title: "Withholding plan",
    description: "Turn your projected balance into clear W-4 and per-paycheck adjustments.",
  },
  "/projections": {
    eyebrow: "Step 5 of 5",
    title: "Future scenarios",
    description: "Model a single year or compare how income and tax decisions change over time.",
  },
  "/imports": {
    eyebrow: "Data utility",
    title: "Import records",
    description: "Bring in paycheck, pension, or non-taxable income data from a CSV file.",
  },
  "/settings": {
    eyebrow: "Plan foundation",
    title: "Profile & data",
    description: "Set household assumptions and keep a portable backup of local records.",
  },
};

const NavigationList = ({
  items,
}: {
  items: Array<{ to: string; label: string; marker: string }>;
}) => (
  <ul>
    {items.map((item) => (
      <li key={item.to}>
        <NavLink
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
        >
          <span className="nav-marker" aria-hidden="true">
            {item.marker}
          </span>
          <span>{item.label}</span>
        </NavLink>
      </li>
    ))}
  </ul>
);

export const AppShell = () => {
  const { pathname } = useLocation();
  const meta = pageMeta[pathname] ?? pageMeta["/"];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="Tax Tracker overview">
          <span className="brand-mark" aria-hidden="true">
            TT
          </span>
          <span>
            <span className="brand-name">Tax Tracker</span>
            <span className="brand-subtitle">Federal planning studio</span>
          </span>
        </Link>

        <nav aria-label="Main navigation">
          <p className="nav-section-label">Your plan</p>
          <NavigationList items={planNavigation} />
          <p className="nav-section-label nav-section-label--spaced">Manage</p>
          <NavigationList items={manageNavigation} />
        </nav>

        <div className="sidebar-note">
          <span className="privacy-dot" aria-hidden="true" />
          <div>
            <strong>Local-first by design</strong>
            <span>Your personal records stay in this browser.</span>
          </div>
        </div>
      </aside>

      <main className="content-area">
        <header className="content-header">
          <div>
            <p className="page-eyebrow">{meta.eyebrow}</p>
            <h1>{meta.title}</h1>
            <p className="page-description">{meta.description}</p>
          </div>
          <Link className="profile-link" to="/settings">
            <span className="profile-link-label">Tax profile</span>
            <span aria-hidden="true">→</span>
          </Link>
        </header>
        <Outlet />
      </main>

      <a
        className="github-fab"
        href={githubUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="View source on GitHub"
        title="View source on GitHub"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 .7a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.57-.29-5.27-1.28-5.27-5.69 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.47.11-3.05 0 0 .96-.31 3.16 1.18a10.9 10.9 0 0 1 5.75 0c2.2-1.49 3.16-1.18 3.16-1.18.62 1.58.23 2.76.11 3.05.74.81 1.18 1.83 1.18 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.07.79 2.16v3.2c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z" />
        </svg>
      </a>
    </div>
  );
};
