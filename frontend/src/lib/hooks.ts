import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./api/client";
import type { AppConfigResponse } from "./api/types";
import { DEFAULT_FILING_STATUS } from "./constants";

/** Fallback config used until the DB row is loaded (or if unavailable). */
export const DEFAULT_APP_CONFIG: AppConfigResponse = {
  filing_status: DEFAULT_FILING_STATUS,
  num_children: 0,
  use_standard_deduction: true,
  itemized_deduction_amount: "0.00",
  age_65_plus: false,
  w2_pay_frequency: "monthly",
};

/**
 * Fetch the singleton app config from the database.
 * Returns `DEFAULT_APP_CONFIG` while loading or on error so callers always
 * have a usable value — they do not need to handle `undefined`.
 */
export const useAppConfig = () => {
  const query = useQuery({
    queryKey: ["app-config"],
    queryFn: apiClient.getConfig,
    staleTime: 60_000,
  });

  return {
    config: query.data ?? DEFAULT_APP_CONFIG,
    isLoading: query.isLoading,
    isError: query.isError,
  };
};
