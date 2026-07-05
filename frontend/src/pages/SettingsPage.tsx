import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../lib/api/client";
import type { AppConfigUpdate, FilingStatus, W2PayFrequency } from "../lib/api/types";
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
    w2_pay_frequency: config?.w2_pay_frequency ?? "monthly",
  };

  const mutation = useMutation({
    mutationFn: (data: AppConfigUpdate) => apiClient.updateConfig(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["app-config"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-prediction"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard-projection"] });
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
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      <div className="settings-layout">
        <div className="settings-card">
          <div className="settings-card-header">
            <h2 className="settings-card-title">Tax Profile</h2>
            <p className="settings-card-description">
              Used across the Dashboard, Projections, and W-4 optimization.
            </p>
          </div>

          <div className="settings-fields">
            <div className="settings-field">
              <label className="settings-label" htmlFor="filing-status">
                Filing Status
              </label>
              <select
                id="filing-status"
                className="settings-select"
                value={current.filing_status ?? "married_filing_jointly"}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...current,
                    ...d,
                    filing_status: e.target.value as FilingStatus,
                  }))
                }
              >
                {FILING_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="settings-field">
              <label className="settings-label" htmlFor="num-children">
                Qualifying Children
              </label>
              <p className="settings-hint">Children eligible for the Child Tax Credit</p>
              <input
                id="num-children"
                type="number"
                className="settings-input settings-input--short"
                min={0}
                value={current.num_children ?? 0}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...current,
                    ...d,
                    num_children: Math.max(0, Number(e.target.value)),
                  }))
                }
              />
            </div>

            <div className="settings-field">
              <p className="settings-label">Deduction Type</p>
              <div className="settings-radio-group">
                <label className="settings-radio" htmlFor="use-standard-deduction">
                  <input
                    id="use-standard-deduction"
                    type="radio"
                    name="deduction-type"
                    checked={current.use_standard_deduction ?? true}
                    onChange={() =>
                      setDraft((d) => ({ ...current, ...d, use_standard_deduction: true }))
                    }
                  />
                  <span>Standard deduction</span>
                </label>
                <label className="settings-radio" htmlFor="use-itemized-deduction">
                  <input
                    id="use-itemized-deduction"
                    type="radio"
                    name="deduction-type"
                    checked={!(current.use_standard_deduction ?? true)}
                    onChange={() =>
                      setDraft((d) => ({ ...current, ...d, use_standard_deduction: false }))
                    }
                  />
                  <span>Itemized deduction</span>
                </label>
              </div>

              {!(current.use_standard_deduction ?? true) && (
                <div className="settings-subfield">
                  <label className="settings-label" htmlFor="itemized-deduction">
                    Itemized Deduction Amount
                  </label>
                  <input
                    id="itemized-deduction"
                    type="number"
                    className="settings-input settings-input--short"
                    min={0}
                    step={100}
                    value={current.itemized_deduction_amount ?? 0}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...current,
                        ...d,
                        itemized_deduction_amount: String(e.target.value),
                      }))
                    }
                  />
                </div>
              )}
            </div>

            <div className="settings-field">
              <label className="settings-checkbox" htmlFor="age-65-plus">
                <input
                  id="age-65-plus"
                  type="checkbox"
                  checked={current.age_65_plus ?? false}
                  onChange={(e) =>
                    setDraft((d) => ({ ...current, ...d, age_65_plus: e.target.checked }))
                  }
                />
                <div>
                  <span className="settings-checkbox-label">Age 65 or older</span>
                  <p className="settings-hint">
                    Adds the additional standard deduction amount for seniors
                  </p>
                </div>
              </label>
            </div>

            <div className="settings-field">
              <label className="settings-label" htmlFor="w2-pay-frequency">
                W-2 Pay Frequency
              </label>
              <p className="settings-hint">
                How often you receive W-2 paychecks — used to calculate remaining pay periods
              </p>
              <select
                id="w2-pay-frequency"
                className="settings-select"
                value={current.w2_pay_frequency ?? "monthly"}
                onChange={(e) =>
                  setDraft((d) => ({
                    ...current,
                    ...d,
                    w2_pay_frequency: e.target.value as W2PayFrequency,
                  }))
                }
              >
                <option value="weekly">Weekly (52/year)</option>
                <option value="biweekly">Biweekly (26/year)</option>
                <option value="semimonthly">Semimonthly (24/year)</option>
                <option value="monthly">Monthly (12/year)</option>
              </select>
            </div>
          </div>

          <div className="settings-footer">
            {mutation.isError && (
              <p className="status-message error">
                {mutation.error instanceof Error ? mutation.error.message : "Save failed"}
              </p>
            )}
            <button
              type="button"
              className="btn-primary"
              onClick={() => mutation.mutate(current)}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Saving…" : saved ? "Saved ✓" : "Save Settings"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
