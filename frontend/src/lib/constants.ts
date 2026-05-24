import type { FilingStatus } from "./api/types";

export const FILING_STATUSES: { value: FilingStatus; label: string }[] = [
  { value: "single", label: "Single" },
  { value: "married_filing_jointly", label: "Married Filing Jointly" },
  { value: "married_filing_separately", label: "Married Filing Separately" },
  { value: "head_of_household", label: "Head of Household" },
];

export const DEFAULT_FILING_STATUS: FilingStatus = "married_filing_jointly";
