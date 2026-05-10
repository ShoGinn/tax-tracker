import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";

const BASE_URL = "";

interface CsvImportResult {
  imported: number;
  skipped: number;
  errors: string[];
  [key: string]: unknown;
}

type ImportType = "paychecks" | "pensions" | "non-taxable";

const IMPORT_TYPES: {
  value: ImportType;
  label: string;
  endpoint: string;
  example: string;
}[] = [
  {
    value: "paychecks",
    label: "W-2 Paychecks",
    endpoint: "/income/paychecks/import-csv",
    example: "paychecks_example.csv",
  },
  {
    value: "pensions",
    label: "1099-R Pensions",
    endpoint: "/income/1099r/import-csv",
    example: "pension_example.csv",
  },
  {
    value: "non-taxable",
    label: "Non-Taxable Income",
    endpoint: "/income/non-taxable/import-csv",
    example: "va_example.csv",
  },
];

const importCsv = async (endpoint: string, file: File): Promise<CsvImportResult> => {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) {
    const body = (await resp.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<CsvImportResult>;
};

// ---------------------------------------------------------------------------
// Importer panel
// ---------------------------------------------------------------------------

const ImportPanel = ({ config }: { config: (typeof IMPORT_TYPES)[number] }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("No file selected");
      return importCsv(config.endpoint, file);
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

  return (
    <div className="card income-form mb-4">
      <p className="helper-text">
        Upload a CSV file to bulk-import {config.label}. The system auto-detects column names and handles currency
        symbols and multiple date formats. See <code>{config.example}</code> in the examples folder for a sample.
      </p>

      {/* Drop zone */}
      <button
        type="button"
        className="csv-drop-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        aria-label="Drop CSV file or click to browse"
      >
        {fileName ? (
          <span className="csv-file-name">{fileName}</span>
        ) : (
          <span className="csv-drop-hint">Drop CSV here or click to browse</span>
        )}
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
      </button>

      {mutation.isError && <p className="form-error">{mutation.error.message}</p>}

      <button
        type="button"
        className="btn-primary mt-2"
        disabled={!file || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "Importing…" : `Import ${config.label}`}
      </button>

      {mutation.data && (
        <div className={`csv-result ${mutation.data.errors.length > 0 ? "csv-result--warn" : "csv-result--ok"}`}>
          <p>
            <strong>Imported:</strong> {mutation.data.imported} &nbsp;
            <strong>Skipped:</strong> {mutation.data.skipped}
          </p>
          {mutation.data.errors.length > 0 && (
            <>
              <p className="form-error">Errors:</p>
              <ul className="csv-error-list">
                {mutation.data.errors.map((e) => (
                  <li key={e}>{e}</li>
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
  const [type, setType] = useState<ImportType>("paychecks");
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
        <div className="panel-header">
          <h2 className="panel-title">Import {config.label}</h2>
        </div>
        <ImportPanel key={type} config={config} />
      </div>
    </div>
  );
};
