import {
  getCustomerSummary,
  type CustomerSummaryResponse,
} from "./api";

export type { CustomerSummaryResponse };

export async function getMemberSummary(
  customerId: string,
  accountId?: string,
): Promise<CustomerSummaryResponse> {
  return getCustomerSummary(customerId, accountId);
}
