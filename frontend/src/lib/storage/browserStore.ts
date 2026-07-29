import Dexie, { type Table } from "dexie";

import type {
  AppConfigResponse,
  AppConfigUpdate,
  CsvImportResult,
  CsvImportType,
  DeleteResponse,
  EmployerCreate,
  EmployerResponse,
  EmployerUpdate,
  NonTaxableIncomeCreate,
  NonTaxableIncomeResponse,
  NonTaxableIncomeUpdate,
  PaycheckCreate,
  PaycheckResponse,
  PaycheckUpdate,
  Retirement1099RCreate,
  Retirement1099RResponse,
  Retirement1099RUpdate,
} from "../api/types";

const BACKUP_VERSION = 1;
const ZERO = "0";

interface StoredPaycheck extends PaycheckCreate {
  id: number;
}

interface StoredPension extends Retirement1099RCreate {
  id: number;
  created_at: string;
  updated_at: string;
}

interface StoredNonTaxable extends NonTaxableIncomeCreate {
  id: number;
}

interface StoredConfig extends AppConfigResponse {
  id: "app";
}

class TaxTrackerDatabase extends Dexie {
  employers!: Table<EmployerResponse, number>;
  paychecks!: Table<StoredPaycheck, number>;
  pensions!: Table<StoredPension, number>;
  nonTaxable!: Table<StoredNonTaxable, number>;
  config!: Table<StoredConfig, string>;

  constructor() {
    super("tax-tracker");
    this.version(1).stores({
      employers: "++id, name",
      paychecks: "++id, employer_id, pay_date, [employer_id+pay_date]",
      pensions: "++id, pay_date",
      nonTaxable: "++id, pay_date",
      config: "id",
    });
  }
}

export const taxTrackerDatabase = new TaxTrackerDatabase();

const defaultConfig: AppConfigResponse = {
  filing_status: "married_filing_jointly",
  num_children: 0,
  use_standard_deduction: true,
  itemized_deduction_amount: ZERO,
  age_65_plus: false,
  w2_pay_frequency: "biweekly",
};

export interface BrowserSnapshot {
  employers: EmployerResponse[];
  paychecks: PaycheckResponse[];
  pensions: Retirement1099RResponse[];
  non_taxable_income: NonTaxableIncomeResponse[];
  config: AppConfigResponse;
}

export interface BrowserBackup extends BrowserSnapshot {
  format: "tax-tracker-browser-backup";
  version: number;
  exported_at: string;
}

const money = (value: string | undefined) => value || ZERO;
const numberValue = (value: string | undefined) => Number(value || 0);
const total = (...values: Array<string | undefined>) =>
  values.reduce((sum, value) => sum + numberValue(value), 0).toFixed(2);

const enrichPaycheck = (record: StoredPaycheck, employer: EmployerResponse): PaycheckResponse => {
  const pretax = total(
    record.deduction_401k,
    record.deduction_403b,
    record.deduction_health_insurance,
    record.deduction_dental_insurance,
    record.deduction_vision_insurance,
    record.deduction_hsa,
    record.deduction_fsa,
    record.deduction_dependent_care_fsa,
    record.deduction_commuter,
    record.deduction_other_pretax,
  );
  const posttax = total(
    record.deduction_roth_401k,
    record.deduction_roth_403b,
    record.deduction_other_posttax,
  );
  const taxes = total(record.federal_withholding, record.social_security, record.medicare);
  const taxable = numberValue(record.gross_wages) + numberValue(record.bonus) - Number(pretax);
  const net =
    numberValue(record.gross_wages) +
    numberValue(record.bonus) -
    Number(pretax) -
    Number(posttax) -
    Number(taxes);
  return {
    ...record,
    employer,
    bonus: money(record.bonus),
    gross_wages: money(record.gross_wages),
    federal_withholding: money(record.federal_withholding),
    social_security: money(record.social_security),
    medicare: money(record.medicare),
    total_pretax_deductions: pretax,
    total_posttax_deductions: posttax,
    total_taxes_withheld: taxes,
    taxable_wages: taxable.toFixed(2),
    net_pay: net.toFixed(2),
    notes: record.notes ?? null,
  };
};

const enrichPension = (record: StoredPension): Retirement1099RResponse => {
  const gross = numberValue(record.gross_amount);
  const pretax = numberValue(record.pretax_deductions);
  const posttax = numberValue(record.posttax_deductions);
  const federal = numberValue(record.federal_withholding);
  return {
    ...record,
    gross_amount: money(record.gross_amount),
    pretax_deductions: money(record.pretax_deductions),
    posttax_deductions: money(record.posttax_deductions),
    federal_withholding: money(record.federal_withholding),
    taxable_amount: (gross - pretax).toFixed(2),
    net_amount: (gross - pretax - posttax - federal).toFixed(2),
    source_description: record.source_description ?? null,
    notes: record.notes ?? null,
  };
};

const parseCsv = (text: string): string[][] => {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === "," && !quoted) {
      row.push(field.trim());
      field = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }
  row.push(field.trim());
  if (row.some(Boolean)) rows.push(row);
  return rows;
};

const normalizeHeader = (value: string) => value.trim().toLowerCase().replaceAll(" ", "_");
const deleted = (): DeleteResponse => ({ message: "Deleted" });
const recordYear = (payDate: string) => Number(payDate.slice(0, 4));

export const browserStore = {
  listEmployers: () => taxTrackerDatabase.employers.toArray(),

  async createEmployer(data: EmployerCreate): Promise<EmployerResponse> {
    const value = {
      ...data,
      ein: data.ein ?? null,
      end_date: data.end_date ?? null,
      notes: data.notes ?? null,
    };
    const id = await taxTrackerDatabase.employers.add(value as EmployerResponse);
    return { ...value, id };
  },

  async updateEmployer(id: number, data: EmployerUpdate): Promise<EmployerResponse> {
    const existing = await taxTrackerDatabase.employers.get(id);
    if (!existing) throw new Error("Employer not found");
    const updated = { ...existing, ...data, id };
    await taxTrackerDatabase.employers.put(updated);
    return updated;
  },

  async deleteEmployer(id: number): Promise<DeleteResponse> {
    await taxTrackerDatabase.transaction(
      "rw",
      taxTrackerDatabase.employers,
      taxTrackerDatabase.paychecks,
      async () => {
        await taxTrackerDatabase.paychecks.where("employer_id").equals(id).delete();
        await taxTrackerDatabase.employers.delete(id);
      },
    );
    return deleted();
  },

  async listPaychecks(year?: number): Promise<PaycheckResponse[]> {
    const [records, employers] = await Promise.all([
      taxTrackerDatabase.paychecks.toArray(),
      taxTrackerDatabase.employers.toArray(),
    ]);
    const employerById = new Map(employers.map((employer) => [employer.id, employer]));
    return records
      .filter((record) => !year || recordYear(record.pay_date) === year)
      .map((record) =>
        enrichPaycheck(
          record,
          employerById.get(record.employer_id) ?? {
            id: record.employer_id,
            name: "Unknown employer",
            ein: null,
            start_date: record.pay_date,
            end_date: null,
            notes: null,
          },
        ),
      )
      .sort((left, right) => right.pay_date.localeCompare(left.pay_date));
  },

  async createPaycheck(data: PaycheckCreate): Promise<PaycheckResponse> {
    const employer = await taxTrackerDatabase.employers.get(data.employer_id);
    if (!employer) throw new Error("Employer not found");
    const id = await taxTrackerDatabase.paychecks.add(data as StoredPaycheck);
    return enrichPaycheck({ ...data, id }, employer);
  },

  async updatePaycheck(id: number, data: PaycheckUpdate): Promise<PaycheckResponse> {
    const existing = await taxTrackerDatabase.paychecks.get(id);
    if (!existing) throw new Error("Paycheck not found");
    const updated = { ...existing, ...data, id };
    const employer = await taxTrackerDatabase.employers.get(updated.employer_id);
    if (!employer) throw new Error("Employer not found");
    await taxTrackerDatabase.paychecks.put(updated);
    return enrichPaycheck(updated, employer);
  },

  async deletePaycheck(id: number): Promise<DeleteResponse> {
    await taxTrackerDatabase.paychecks.delete(id);
    return deleted();
  },

  async listPensions(year?: number): Promise<Retirement1099RResponse[]> {
    return (await taxTrackerDatabase.pensions.toArray())
      .filter((record) => !year || recordYear(record.pay_date) === year)
      .map(enrichPension)
      .sort((left, right) => right.pay_date.localeCompare(left.pay_date));
  },

  async createPension(data: Retirement1099RCreate): Promise<Retirement1099RResponse> {
    const now = new Date().toISOString();
    const value = { ...data, created_at: now, updated_at: now };
    const id = await taxTrackerDatabase.pensions.add(value as StoredPension);
    return enrichPension({ ...value, id });
  },

  async updatePension(id: number, data: Retirement1099RUpdate): Promise<Retirement1099RResponse> {
    const existing = await taxTrackerDatabase.pensions.get(id);
    if (!existing) throw new Error("Pension payment not found");
    const updated = { ...existing, ...data, id, updated_at: new Date().toISOString() };
    await taxTrackerDatabase.pensions.put(updated);
    return enrichPension(updated);
  },

  async deletePension(id: number): Promise<DeleteResponse> {
    await taxTrackerDatabase.pensions.delete(id);
    return deleted();
  },

  async listNonTaxableIncome(year?: number): Promise<NonTaxableIncomeResponse[]> {
    return (await taxTrackerDatabase.nonTaxable.toArray())
      .filter((record) => !year || recordYear(record.pay_date) === year)
      .map((record) => ({
        ...record,
        amount: money(record.amount),
        source_type: record.source_type ?? null,
        notes: record.notes ?? null,
      }))
      .sort((left, right) => right.pay_date.localeCompare(left.pay_date));
  },

  async createNonTaxableIncome(data: NonTaxableIncomeCreate): Promise<NonTaxableIncomeResponse> {
    const id = await taxTrackerDatabase.nonTaxable.add(data as StoredNonTaxable);
    return {
      ...data,
      id,
      amount: money(data.amount),
      source_type: data.source_type ?? null,
      notes: data.notes ?? null,
    };
  },

  async updateNonTaxableIncome(
    id: number,
    data: NonTaxableIncomeUpdate,
  ): Promise<NonTaxableIncomeResponse> {
    const existing = await taxTrackerDatabase.nonTaxable.get(id);
    if (!existing) throw new Error("Non-taxable payment not found");
    const updated = { ...existing, ...data, id };
    await taxTrackerDatabase.nonTaxable.put(updated);
    return {
      ...updated,
      source_type: updated.source_type ?? null,
      notes: updated.notes ?? null,
    };
  },

  async deleteNonTaxableIncome(id: number): Promise<DeleteResponse> {
    await taxTrackerDatabase.nonTaxable.delete(id);
    return deleted();
  },

  async getConfig(): Promise<AppConfigResponse> {
    const stored = await taxTrackerDatabase.config.get("app");
    return stored ?? defaultConfig;
  },

  async updateConfig(update: AppConfigUpdate): Promise<AppConfigResponse> {
    const value: StoredConfig = { ...(await this.getConfig()), ...update, id: "app" };
    await taxTrackerDatabase.config.put(value);
    return value;
  },

  async snapshot(year?: number): Promise<BrowserSnapshot> {
    const [employers, paychecks, pensions, nonTaxable, config] = await Promise.all([
      this.listEmployers(),
      this.listPaychecks(year),
      this.listPensions(year),
      this.listNonTaxableIncome(year),
      this.getConfig(),
    ]);
    return {
      employers,
      paychecks,
      pensions,
      non_taxable_income: nonTaxable,
      config,
    };
  },

  async exportBackup(): Promise<BrowserBackup> {
    return {
      ...(await this.snapshot()),
      format: "tax-tracker-browser-backup",
      version: BACKUP_VERSION,
      exported_at: new Date().toISOString(),
    };
  },

  async importBackup(backup: BrowserBackup): Promise<void> {
    if (backup.format !== "tax-tracker-browser-backup" || backup.version !== BACKUP_VERSION) {
      throw new Error("Unsupported Tax Tracker backup");
    }
    await taxTrackerDatabase.transaction(
      "rw",
      taxTrackerDatabase.employers,
      taxTrackerDatabase.paychecks,
      taxTrackerDatabase.pensions,
      taxTrackerDatabase.nonTaxable,
      taxTrackerDatabase.config,
      async () => {
        await Promise.all([
          taxTrackerDatabase.employers.clear(),
          taxTrackerDatabase.paychecks.clear(),
          taxTrackerDatabase.pensions.clear(),
          taxTrackerDatabase.nonTaxable.clear(),
          taxTrackerDatabase.config.clear(),
        ]);
        const paychecks = backup.paychecks.map(
          ({
            employer: _employer,
            taxable_wages: _taxable,
            total_taxes_withheld: _taxes,
            total_pretax_deductions: _pretax,
            total_posttax_deductions: _posttax,
            net_pay: _net,
            ...record
          }) => record as StoredPaycheck,
        );
        await Promise.all([
          taxTrackerDatabase.employers.bulkPut(backup.employers),
          taxTrackerDatabase.paychecks.bulkPut(paychecks),
          taxTrackerDatabase.pensions.bulkPut(backup.pensions as StoredPension[]),
          taxTrackerDatabase.nonTaxable.bulkPut(backup.non_taxable_income as StoredNonTaxable[]),
          taxTrackerDatabase.config.put({ ...backup.config, id: "app" }),
        ]);
      },
    );
  },

  async importCsv(type: CsvImportType, file: File): Promise<CsvImportResult> {
    const rows = parseCsv(await file.text());
    if (rows.length === 0) {
      return { imported: 0, skipped: 0, total_rows: 0, errors: [] };
    }
    const headers = rows[0].map(normalizeHeader);
    const errors: CsvImportResult["errors"] = [];
    let imported = 0;
    for (const [index, values] of rows.slice(1).entries()) {
      const data = Object.fromEntries(
        headers.map((header, column) => [header, values[column] ?? ""]),
      );
      try {
        if (type === "paychecks") {
          const paycheck = {
            ...(data as unknown as PaycheckCreate),
            employer_id: Number(data.employer_id),
          };
          const duplicate = (
            await taxTrackerDatabase.paychecks
              .where("[employer_id+pay_date]")
              .equals([paycheck.employer_id, paycheck.pay_date])
              .toArray()
          ).some((record) => record.gross_wages === paycheck.gross_wages);
          if (duplicate) throw new Error("Duplicate paycheck skipped");
          await this.createPaycheck(paycheck);
        } else if (type === "pensions") {
          const pension = data as unknown as Retirement1099RCreate;
          const duplicate = (
            await taxTrackerDatabase.pensions.where("pay_date").equals(pension.pay_date).toArray()
          ).some((record) => record.gross_amount === pension.gross_amount);
          if (duplicate) throw new Error("Duplicate pension payment skipped");
          await this.createPension(pension);
        } else {
          const payment = data as unknown as NonTaxableIncomeCreate;
          const duplicate = (
            await taxTrackerDatabase.nonTaxable.where("pay_date").equals(payment.pay_date).toArray()
          ).some(
            (record) =>
              record.amount === payment.amount &&
              (record.source_type ?? "") === (payment.source_type ?? ""),
          );
          if (duplicate) throw new Error("Duplicate non-taxable payment skipped");
          await this.createNonTaxableIncome(payment);
        }
        imported += 1;
      } catch (error) {
        errors.push({
          row: index + 2,
          error: error instanceof Error ? error.message : "Import failed",
          data,
        });
      }
    }
    return {
      imported,
      skipped: errors.length,
      total_rows: rows.length - 1,
      errors,
    };
  },
};
