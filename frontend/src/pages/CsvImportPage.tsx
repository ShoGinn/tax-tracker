import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { apiClient } from "../lib/api/client";
import type { CsvImportType } from "../lib/api/types";

const IMPORT_TYPES: {
  value: CsvImportType;
  label: string;
  example: string;
}[] = [
  {
    value: "paychecks",
    label: "W-2 Paychecks",
    example: "paychecks_example.csv",
  },
  {
    value: "pensions",
    label: "1099-R Pensions",
    example: "pension_example.csv",
  },
  {
    value: "non-taxable",
    label: "Non-Taxable Income",
    example: "va_example.csv",
  },
];

// ---------------------------------------------------------------------------
// Importer panel
// ---------------------------------------------------------------------------

const ImportPanel = ({ config }: { config: (typeof IMPORT_TYPES)[number] }) => {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      return apiClient.importCsv(config.value, file);
    },
    onSuccess: () => {
      const queryKey =
        config.value === "paychecks"
          ? ["paychecks"]
          : config.value === "pensions"
            ? ["pensions"]
            : ["non-taxable"];
      void queryClient.invalidateQueries({ queryKey });
    },
  });

  const handleFile = (f: File) => {
    setFile(f);
    setFileName(f.name);
    mutation.reset();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  };

  const clearFile = () => {
    setFile(null);
    setFileName(null);
    mutation.reset();
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="card income-form mb-4">
      <p className="helper-text">
        Upload a CSV file to bulk-import {config.label} into this browser. Column headers should
        match the sample, and dates should use YYYY-MM-DD. Duplicate records are reported and
        skipped. See <code>{config.example}</code> in the examples folder for a sample.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        style={{ display: "none" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />

      {file ? (
        <div className="csv-selected-file">
          <span className="csv-file-name">📄 {fileName}</span>
          <div className="csv-selected-actions">
            <button type="button" className="btn-ghost-sm" onClick={clearFile}>
              Change
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? "Importing…" : "Import"}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="csv-drop-zone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          aria-label="Drop CSV file or click to browse"
        >
          <span className="csv-drop-hint">Drop CSV here or click to browse</span>
        </button>
      )}

      {mutation.isError && <p className="form-error mt-2">{mutation.error.message}</p>}

      {mutation.data && (
        <div
          className={`csv-result ${mutation.data.errors.length > 0 ? "csv-result--warn" : "csv-result--ok"}`}
        >
          <p>
            <strong>Imported:</strong> {mutation.data.imported} &nbsp;
            <strong>Skipped:</strong> {mutation.data.skipped}
          </p>
          {mutation.data.errors.length > 0 && (
            <>
              <p className="form-error">Errors:</p>
              <p className="helper-text">
                Duplicate records are skipped safely. Correct other reported rows and import the
                file again.
              </p>
              <ul className="csv-error-list">
                {mutation.data.errors.map((e) => (
                  <li key={`${e.row}-${e.error}`}>
                    Row {e.row}: {e.error}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export const CsvImportPage = () => {
  const [type, setType] = useState<CsvImportType>("paychecks");
  const config = IMPORT_TYPES.find((t) => t.value === type) ?? IMPORT_TYPES[0];

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">CSV Import</h1>
      </div>

      <div className="tab-bar">
        {IMPORT_TYPES.map((t) => (
          <button
            key={t.value}
            type="button"
            className={`tab-btn${type === t.value ? " active" : ""}`}
            onClick={() => setType(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-panel">
        <ImportPanel key={type} config={config} />
      </div>
    </div>
  );
};
