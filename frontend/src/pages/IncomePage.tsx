import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../lib/api/client";
import type {
  EmployerCreate,
  NonTaxableIncomeCreate,
  PaycheckCreate,
  Retirement1099RCreate,
} from "../lib/api/types";
import { formatCurrency, parseDecimalString } from "../lib/money";

type Tab = "paychecks" | "pensions" | "non-taxable";

const currentYear = new Date().getFullYear();

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

const YearFilter = ({ year, onChange }: { year: number; onChange: (y: number) => void }) => (
  <select
    className="year-select"
    value={year}
    onChange={(e) => onChange(Number(e.target.value))}
    aria-label="Filter by tax year"
  >
    {Array.from({ length: 5 }, (_, i) => currentYear - i).map((y) => (
      <option key={y} value={y}>
        {y}
      </option>
    ))}
  </select>
);

const DeleteButton = ({ onConfirm }: { onConfirm: () => void }) => {
  const [confirm, setConfirm] = useState(false);

  if (confirm) {
    return (
      <span className="delete-confirm">
        Sure?{" "}
        <button type="button" className="btn-danger-sm" onClick={onConfirm}>
          Yes
        </button>{" "}
        <button type="button" className="btn-ghost-sm" onClick={() => setConfirm(false)}>
          No
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      className="btn-ghost-sm"
      onClick={() => setConfirm(true)}
      aria-label="Delete"
    >
      ✕
    </button>
  );
};

// ---------------------------------------------------------------------------
// Employer quick-create inline form
// ---------------------------------------------------------------------------

const EmployerQuickCreate = ({ onCreated }: { onCreated: (id: number) => void }) => {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState(`${String(currentYear)}-01-01`);

  const mutation = useMutation({
    mutationFn: (data: EmployerCreate) => apiClient.createEmployer(data),
    onSuccess: (employer) => {
      queryClient.invalidateQueries({ queryKey: ["employers"] });
      onCreated(employer.id);
      setName("");
    },
  });

  return (
    <form
      className="inline-form"
      onSubmit={(e) => {
        e.preventDefault();
        mutation.mutate({ name: name.trim(), start_date: startDate });
      }}
    >
      <input
        type="text"
        placeholder="Employer name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        className="form-input"
      />
      <input
        type="date"
        value={startDate}
        onChange={(e) => setStartDate(e.target.value)}
        required
        className="form-input"
      />
      <button type="submit" className="btn-primary" disabled={mutation.isPending}>
        {mutation.isPending ? "Adding…" : "Add employer"}
      </button>
      {mutation.isError && <span className="form-error">{mutation.error.message}</span>}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Paychecks tab
// ---------------------------------------------------------------------------

const PaychecksTab = ({ year }: { year: number }) => {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [showEmployerForm, setShowEmployerForm] = useState(false);

  const { data: employers = [] } = useQuery({
    queryKey: ["employers"],
    queryFn: apiClient.listEmployers,
  });

  const {
    data: paychecks = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["paychecks", year],
    queryFn: () => apiClient.listPaychecks(year),
  });

  const deleteMutation = useMutation({
    mutationFn: apiClient.deletePaycheck,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["paychecks", year] }),
  });

  const createMutation = useMutation({
    mutationFn: (data: PaycheckCreate) => apiClient.createPaycheck(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paychecks", year] });
      setShowForm(false);
    },
  });

  const totalGross = paychecks.reduce(
    (s, p) => s + parseDecimalString(p.gross_wages) + parseDecimalString(p.bonus),
    0,
  );
  const totalBonus = paychecks.reduce((s, p) => s + parseDecimalString(p.bonus), 0);
  const totalTaxable = paychecks.reduce((s, p) => s + parseDecimalString(p.taxable_wages), 0);
  const totalWithholding = paychecks.reduce(
    (s, p) => s + parseDecimalString(p.federal_withholding),
    0,
  );
  const totalFica = paychecks.reduce(
    (s, p) => s + parseDecimalString(p.social_security) + parseDecimalString(p.medicare),
    0,
  );
  const totalNet = paychecks.reduce((s, p) => s + parseDecimalString(p.net_pay), 0);
  const hasBonus = totalBonus > 0;

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">W-2 Paychecks</h2>
        <div className="panel-actions">
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setShowEmployerForm((v) => !v)}
          >
            {showEmployerForm ? "Hide employer form" : "+ Add employer"}
          </button>
          <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "+ Add paycheck"}
          </button>
        </div>
      </div>

      {showEmployerForm && (
        <div className="card mb-4">
          <h3 className="card-title">New Employer</h3>
          <EmployerQuickCreate onCreated={() => setShowEmployerForm(false)} />
        </div>
      )}

      {showForm && (
        <PaycheckForm
          employers={employers}
          year={year}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}

      {isLoading && <p className="loading-text">Loading…</p>}
      {isError && <p className="error-text">{(error as Error).message}</p>}

      {!isLoading &&
        !isError &&
        (paychecks.length === 0 ? (
          <p className="empty-text">No paychecks for {year}. Add one above.</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Employer</th>
                  <th className="num">Gross wages</th>
                  {hasBonus && <th className="num">Bonus</th>}
                  <th className="num">Taxable wages</th>
                  <th className="num">Fed. withheld</th>
                  <th className="num">FICA</th>
                  <th className="num">Net pay</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {paychecks.map((p) => {
                  const fica =
                    parseDecimalString(p.social_security) + parseDecimalString(p.medicare);
                  return (
                    <tr key={p.id}>
                      <td>{p.pay_date}</td>
                      <td>{p.employer.name}</td>
                      <td className="num">{formatCurrency(parseDecimalString(p.gross_wages))}</td>
                      {hasBonus && (
                        <td className="num">
                          {parseDecimalString(p.bonus) > 0
                            ? formatCurrency(parseDecimalString(p.bonus))
                            : "—"}
                        </td>
                      )}
                      <td className="num">{formatCurrency(parseDecimalString(p.taxable_wages))}</td>
                      <td className="num">
                        {formatCurrency(parseDecimalString(p.federal_withholding))}
                      </td>
                      <td className="num">{formatCurrency(fica)}</td>
                      <td className="num">{formatCurrency(parseDecimalString(p.net_pay))}</td>
                      <td>
                        <DeleteButton onConfirm={() => deleteMutation.mutate(p.id)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="totals-row">
                  <td colSpan={2}>
                    <strong>{paychecks.length} paychecks</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalGross)}</strong>
                  </td>
                  {hasBonus && (
                    <td className="num">
                      <strong>{formatCurrency(totalBonus)}</strong>
                    </td>
                  )}
                  <td className="num">
                    <strong>{formatCurrency(totalTaxable)}</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalWithholding)}</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalFica)}</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalNet)}</strong>
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Paycheck create form
// ---------------------------------------------------------------------------

const PaycheckForm = ({
  employers,
  year,
  onSubmit,
  isPending,
  error,
}: {
  employers: { id: number; name: string }[];
  year: number;
  onSubmit: (data: PaycheckCreate) => void;
  isPending: boolean;
  error?: string;
}) => {
  const [fields, setFields] = useState<PaycheckCreate>({
    employer_id: employers[0]?.id ?? 0,
    pay_date: `${year}-01-01`,
    gross_wages: "",
    bonus: "0",
    federal_withholding: "0",
    social_security: "0",
    medicare: "0",
    deduction_401k: "0",
    deduction_health_insurance: "0",
    deduction_dental_insurance: "0",
    deduction_vision_insurance: "0",
    deduction_hsa: "0",
    deduction_other_pretax: "0",
    deduction_roth_401k: "0",
    deduction_other_posttax: "0",
  });

  const set = (key: keyof PaycheckCreate, val: string | number) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <form
      className="card income-form mb-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(fields);
      }}
    >
      <h3 className="card-title">New Paycheck</h3>

      {employers.length === 0 ? (
        <p className="form-error">Create an employer first before adding a paycheck.</p>
      ) : (
        <>
          <div className="form-grid">
            <label className="form-label">
              Employer
              <select
                className="form-input"
                value={fields.employer_id}
                onChange={(e) => set("employer_id", Number(e.target.value))}
                required
              >
                {employers.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="form-label">
              Pay date
              <input
                type="date"
                className="form-input"
                value={fields.pay_date}
                onChange={(e) => set("pay_date", e.target.value)}
                required
              />
            </label>

            <label className="form-label">
              Gross wages
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.gross_wages}
                onChange={(e) => set("gross_wages", e.target.value)}
                required
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Bonus
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.bonus}
                onChange={(e) => set("bonus", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Fed. withholding
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.federal_withholding}
                onChange={(e) => set("federal_withholding", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Social Security
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.social_security}
                onChange={(e) => set("social_security", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Medicare
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.medicare}
                onChange={(e) => set("medicare", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              401(k)
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_401k}
                onChange={(e) => set("deduction_401k", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Health insurance
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_health_insurance}
                onChange={(e) => set("deduction_health_insurance", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Dental
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_dental_insurance}
                onChange={(e) => set("deduction_dental_insurance", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Vision
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_vision_insurance}
                onChange={(e) => set("deduction_vision_insurance", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              HSA
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_hsa}
                onChange={(e) => set("deduction_hsa", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Other pre-tax
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_other_pretax}
                onChange={(e) => set("deduction_other_pretax", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Roth 401(k)
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_roth_401k}
                onChange={(e) => set("deduction_roth_401k", e.target.value)}
                placeholder="0.00"
              />
            </label>

            <label className="form-label">
              Other post-tax
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={fields.deduction_other_posttax}
                onChange={(e) => set("deduction_other_posttax", e.target.value)}
                placeholder="0.00"
              />
            </label>
          </div>

          {error && <p className="form-error">{error}</p>}

          <button type="submit" className="btn-primary mt-2" disabled={isPending}>
            {isPending ? "Saving…" : "Save paycheck"}
          </button>
        </>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// 1099-R Pensions tab
// ---------------------------------------------------------------------------

const PensionsTab = ({ year }: { year: number }) => {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const {
    data: pensions = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["pensions", year],
    queryFn: () => apiClient.listPensions(year),
  });

  const deleteMutation = useMutation({
    mutationFn: apiClient.deletePension,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["pensions", year] }),
  });

  const createMutation = useMutation({
    mutationFn: (data: Retirement1099RCreate) => apiClient.createPension(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pensions", year] });
      setShowForm(false);
    },
  });

  const totalGross = pensions.reduce((s, p) => s + parseDecimalString(p.gross_amount), 0);
  const totalWithholding = pensions.reduce(
    (s, p) => s + parseDecimalString(p.federal_withholding),
    0,
  );
  const totalNet = pensions.reduce((s, p) => s + parseDecimalString(p.net_amount), 0);

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">1099-R Pension / Retirement</h2>
        <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ Add 1099-R"}
        </button>
      </div>

      {showForm && (
        <PensionForm
          year={year}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}

      {isLoading && <p className="loading-text">Loading…</p>}
      {isError && <p className="error-text">{(error as Error).message}</p>}

      {!isLoading &&
        !isError &&
        (pensions.length === 0 ? (
          <p className="empty-text">No 1099-R entries for {year}. Add one above.</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Source</th>
                  <th className="num">Gross</th>
                  <th className="num">Pre-tax deductions</th>
                  <th className="num">Taxable</th>
                  <th className="num">Fed. withheld</th>
                  <th className="num">Net</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pensions.map((p) => (
                  <tr key={p.id}>
                    <td>{p.pay_date}</td>
                    <td>{p.source_description ?? "—"}</td>
                    <td className="num">{formatCurrency(parseDecimalString(p.gross_amount))}</td>
                    <td className="num">
                      {formatCurrency(parseDecimalString(p.pretax_deductions))}
                    </td>
                    <td className="num">{formatCurrency(parseDecimalString(p.taxable_amount))}</td>
                    <td className="num">
                      {formatCurrency(parseDecimalString(p.federal_withholding))}
                    </td>
                    <td className="num">{formatCurrency(parseDecimalString(p.net_amount))}</td>
                    <td>
                      <DeleteButton onConfirm={() => deleteMutation.mutate(p.id)} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="totals-row">
                  <td colSpan={2}>
                    <strong>{pensions.length} entries</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalGross)}</strong>
                  </td>
                  <td />
                  <td />
                  <td className="num">
                    <strong>{formatCurrency(totalWithholding)}</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalNet)}</strong>
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        ))}
    </div>
  );
};

const PensionForm = ({
  year,
  onSubmit,
  isPending,
  error,
}: {
  year: number;
  onSubmit: (data: Retirement1099RCreate) => void;
  isPending: boolean;
  error?: string;
}) => {
  const [fields, setFields] = useState<Retirement1099RCreate>({
    pay_date: `${year}-01-01`,
    gross_amount: "",
    pretax_deductions: "0",
    posttax_deductions: "0",
    federal_withholding: "0",
    source_description: "",
  });

  const set = (key: keyof Retirement1099RCreate, val: string) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <form
      className="card income-form mb-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(fields);
      }}
    >
      <h3 className="card-title">New 1099-R Entry</h3>
      <div className="form-grid">
        <label className="form-label">
          Pay date
          <input
            type="date"
            className="form-input"
            value={fields.pay_date}
            onChange={(e) => set("pay_date", e.target.value)}
            required
          />
        </label>

        <label className="form-label">
          Gross amount
          <input
            type="number"
            step="0.01"
            min="0"
            className="form-input"
            value={fields.gross_amount}
            onChange={(e) => set("gross_amount", e.target.value)}
            required
            placeholder="0.00"
          />
        </label>

        <label className="form-label">
          Pre-tax deductions
          <input
            type="number"
            step="0.01"
            min="0"
            className="form-input"
            value={fields.pretax_deductions}
            onChange={(e) => set("pretax_deductions", e.target.value)}
            placeholder="0.00"
          />
        </label>

        <label className="form-label">
          Post-tax deductions
          <input
            type="number"
            step="0.01"
            min="0"
            className="form-input"
            value={fields.posttax_deductions}
            onChange={(e) => set("posttax_deductions", e.target.value)}
            placeholder="0.00"
          />
        </label>

        <label className="form-label">
          Fed. withholding
          <input
            type="number"
            step="0.01"
            min="0"
            className="form-input"
            value={fields.federal_withholding}
            onChange={(e) => set("federal_withholding", e.target.value)}
            placeholder="0.00"
          />
        </label>

        <label className="form-label">
          Source description
          <input
            type="text"
            className="form-input"
            value={fields.source_description ?? ""}
            onChange={(e) => set("source_description", e.target.value)}
            placeholder="e.g. Retirement distribution"
          />
        </label>
      </div>

      {error && <p className="form-error">{error}</p>}
      <button type="submit" className="btn-primary mt-2" disabled={isPending}>
        {isPending ? "Saving…" : "Save 1099-R"}
      </button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Non-taxable income tab
// ---------------------------------------------------------------------------

const NonTaxableTab = ({ year }: { year: number }) => {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);

  const {
    data: entries = [],
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["non-taxable", year],
    queryFn: () => apiClient.listNonTaxableIncome(year),
  });

  const deleteMutation = useMutation({
    mutationFn: apiClient.deleteNonTaxableIncome,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["non-taxable", year] }),
  });

  const createMutation = useMutation({
    mutationFn: (data: NonTaxableIncomeCreate) => apiClient.createNonTaxableIncome(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["non-taxable", year] });
      setShowForm(false);
    },
  });

  const totalAmount = entries.reduce((s, e) => s + parseDecimalString(e.amount), 0);

  return (
    <div className="tab-panel">
      <div className="panel-header">
        <h2 className="panel-title">Non-taxable Income</h2>
        <button type="button" className="btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ Add entry"}
        </button>
      </div>

      {showForm && (
        <NonTaxableForm
          year={year}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
          error={createMutation.error?.message}
        />
      )}

      {isLoading && <p className="loading-text">Loading…</p>}
      {isError && <p className="error-text">{(error as Error).message}</p>}

      {!isLoading &&
        !isError &&
        (entries.length === 0 ? (
          <p className="empty-text">No non-taxable entries for {year}. Add one above.</p>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Source</th>
                  <th className="num">Amount</th>
                  <th>Notes</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id}>
                    <td>{e.pay_date}</td>
                    <td>{e.source_type ?? "—"}</td>
                    <td className="num">{formatCurrency(parseDecimalString(e.amount))}</td>
                    <td>{e.notes ?? "—"}</td>
                    <td>
                      <DeleteButton onConfirm={() => deleteMutation.mutate(e.id)} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="totals-row">
                  <td colSpan={2}>
                    <strong>{entries.length} entries</strong>
                  </td>
                  <td className="num">
                    <strong>{formatCurrency(totalAmount)}</strong>
                  </td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </table>
          </div>
        ))}
    </div>
  );
};

const NonTaxableForm = ({
  year,
  onSubmit,
  isPending,
  error,
}: {
  year: number;
  onSubmit: (data: NonTaxableIncomeCreate) => void;
  isPending: boolean;
  error?: string;
}) => {
  const [fields, setFields] = useState<NonTaxableIncomeCreate>({
    pay_date: `${year}-01-01`,
    amount: "",
    source_type: "",
    notes: "",
  });

  const set = (key: keyof NonTaxableIncomeCreate, val: string) =>
    setFields((prev) => ({ ...prev, [key]: val }));

  return (
    <form
      className="card income-form mb-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(fields);
      }}
    >
      <h3 className="card-title">New Non-taxable Entry</h3>
      <div className="form-grid">
        <label className="form-label">
          Pay date
          <input
            type="date"
            className="form-input"
            value={fields.pay_date}
            onChange={(e) => set("pay_date", e.target.value)}
            required
          />
        </label>

        <label className="form-label">
          Amount
          <input
            type="number"
            step="0.01"
            min="0"
            className="form-input"
            value={fields.amount}
            onChange={(e) => set("amount", e.target.value)}
            required
            placeholder="0.00"
          />
        </label>

        <label className="form-label">
          Source type
          <input
            type="text"
            className="form-input"
            value={fields.source_type ?? ""}
            onChange={(e) => set("source_type", e.target.value)}
            placeholder="e.g. Non-taxable benefit"
          />
        </label>

        <label className="form-label">
          Notes
          <input
            type="text"
            className="form-input"
            value={fields.notes ?? ""}
            onChange={(e) => set("notes", e.target.value)}
            placeholder="Optional"
          />
        </label>
      </div>

      {error && <p className="form-error">{error}</p>}
      <button type="submit" className="btn-primary mt-2" disabled={isPending}>
        {isPending ? "Saving…" : "Save entry"}
      </button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export const IncomePage = () => {
  const [tab, setTab] = useState<Tab>("paychecks");
  const [year, setYear] = useState(currentYear);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Income</h1>
        <YearFilter year={year} onChange={setYear} />
      </div>

      <div className="tab-bar">
        {(["paychecks", "pensions", "non-taxable"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`tab-btn${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "paychecks"
              ? "W-2 Paychecks"
              : t === "pensions"
                ? "1099-R Pensions"
                : "Non-taxable"}
          </button>
        ))}
      </div>

      {tab === "paychecks" && <PaychecksTab year={year} />}
      {tab === "pensions" && <PensionsTab year={year} />}
      {tab === "non-taxable" && <NonTaxableTab year={year} />}
    </div>
  );
};
