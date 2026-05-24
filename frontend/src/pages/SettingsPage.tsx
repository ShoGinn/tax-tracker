import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../lib/api/client";
import type { AppConfigUpdate, FilingStatus } from "../lib/api/types";
import { FILING_STATUSES } from "../lib/constants";

export const SettingsPage = () => {
  const queryClient = useQueryClient();

  const configQuery = useQuery({
    queryKey: ["app-config"],
    queryFn: apiClient.getConfig,
  });

  const [draft, setDraft] = useState<AppConfigUpdate | null>(null);
  const [saved, setSaved] = useState(false);

  const config = configQuery.data;
  const current: AppConfigUpdate = draft ?? {
    filing_status: config?.filing_status,
    num_children: config?.num_children ?? 0,
    use_standard_deduction: config?.use_standard_deduction ?? true,
    itemized_deduction_amount: config?.itemized_deduction_amount,
    age_65_plus: config?.age_65_plus ?? false,
  };

  const mutation = useMutation({
    mutationFn: (data: AppConfigUpdate) => apiClient.updateConfig(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["app-config"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-prediction"] });
      setDraft(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  if (configQuery.isLoading) return <p className="status-message">Loading settings…</p>;
  if (configQuery.isError)
    return (
      <p className="status-message error">
        {configQuery.error instanceof Error ? configQuery.error.message : "Failed to load settings"}
      </p>
    );

  return (
    <section className="settings-page">
      <h2>App Settings</h2>
      <p className="settings-description">
        These settings are used across the whole app — the Dashboard predictions, Projections, and W-4 optimization all
        read from here.
      </p>

      <article className="metric-card config-card">
        <p className="metric-label">Tax Profile</p>
        <div className="config-form">
          <label className="config-field" htmlFor="filing-status">
            <span>Filing Status</span>
            <select
              id="filing-status"
              value={current.filing_status ?? "married_filing_jointly"}
              onChange={(e) => setDraft((d) => ({ ...current, ...d, filing_status: e.target.value as FilingStatus }))}
            >
              {FILING_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>

          <label className="config-field" htmlFor="num-children">
            <span>Qualifying Children</span>
            <input
              id="num-children"
              type="number"
              min={0}
              value={current.num_children ?? 0}
              onChange={(e) =>
                setDraft((d) => ({ ...current, ...d, num_children: Math.max(0, Number(e.target.value)) }))
              }
            />
          </label>

          <label className="config-field config-checkbox" htmlFor="age-65-plus">
            <input
              id="age-65-plus"
              type="checkbox"
              checked={current.age_65_plus ?? false}
              onChange={(e) => setDraft((d) => ({ ...current, ...d, age_65_plus: e.target.checked }))}
            />
            <span>Age 65+ (additional standard deduction)</span>
          </label>

          <label className="config-field config-checkbox" htmlFor="use-standard-deduction">
            <input
              id="use-standard-deduction"
              type="checkbox"
              checked={current.use_standard_deduction ?? true}
              onChange={(e) => setDraft((d) => ({ ...current, ...d, use_standard_deduction: e.target.checked }))}
            />
            <span>Use standard deduction</span>
          </label>

          {!(current.use_standard_deduction ?? true) && (
            <label className="config-field" htmlFor="itemized-deduction">
              <span>Itemized Deduction Amount</span>
              <input
                id="itemized-deduction"
                type="number"
                min={0}
                step={100}
                value={current.itemized_deduction_amount ?? 0}
                onChange={(e) =>
                  setDraft((d) => ({ ...current, ...d, itemized_deduction_amount: String(e.target.value) }))
                }
              />
            </label>
          )}

          <button
            type="button"
            className="btn-primary"
            onClick={() => mutation.mutate(current)}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Saving…" : saved ? "Saved ✓" : "Save Settings"}
          </button>

          {mutation.isError && (
            <p className="status-message error">
              {mutation.error instanceof Error ? mutation.error.message : "Save failed"}
            </p>
          )}
        </div>
      </article>
    </section>
  );
};
