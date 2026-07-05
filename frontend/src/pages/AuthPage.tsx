export const AuthPage = () => {
  return (
    <section className="module-card auth-card">
      <h2>Authentication Placeholder</h2>
      <p>
        This milestone includes UI placeholders only. Backend authentication is not implemented yet,
        so all current API requests continue using unauthenticated access.
      </p>
      <form className="auth-form" aria-label="Authentication placeholder form">
        <label>
          Email
          <input type="email" placeholder="you@example.com" disabled />
        </label>
        <label>
          Password
          <input type="password" placeholder="••••••••" disabled />
        </label>
        <button type="button" disabled>
          Sign in (coming soon)
        </button>
      </form>
    </section>
  );
};
