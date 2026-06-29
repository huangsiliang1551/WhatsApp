import { describe, expect, it } from "vitest";

import {
  normalizeTaskMonitorAlertEventResponse,
  normalizeTaskMonitorRowResponse,
  normalizeTaskMonitorSummaryResponse,
} from "./api";

describe("task monitor api normalizers", () => {
  it("maps camelCase task monitor rows into the snake_case frontend contract", () => {
    const row = normalizeTaskMonitorRowResponse({
      packageId: "pkg-1",
      accountId: "acct-1",
      userId: "user-1",
      publicUserId: "pub-u1",
      siteId: "site-1",
      siteKey: "site-cn",
      batchId: "batch-1",
      dayNo: 2,
      progressLabel: "2/5",
      status: "active",
      currentItemIndex: 2,
      plannedAmount: 100,
      systemGeneratedAmount: 90,
      manualAddedAmount: 10,
      effectiveAmount: 100,
      hasManualAdd: true,
      dayPlannedAmount: 300,
      daySystemGeneratedAmount: 260,
      dayManualAddedAmount: 40,
      dayEffectiveAmount: 300,
      manualAddedItemCount: 2,
      latestManualAddOperatorId: "operator-h5-member-auth",
      latestManualAddAt: "2026-06-24T06:00:00Z",
      currentProductId: "item-2",
      currentProductName: "Starter Product B",
      currentProductAmount: 30,
      currentProductOrigin: "system_generated",
      totalRealRechargeAmount: 120,
      totalWithdrawAmount: 20,
      estimatedRewardAmount: 15,
      claimedAt: "2026-06-24T00:00:00Z",
      completedAt: null,
    });

    expect(row).toEqual({
      package_id: "pkg-1",
      account_id: "acct-1",
      user_id: "user-1",
      public_user_id: "pub-u1",
      site_id: "site-1",
      site_key: "site-cn",
      batch_id: "batch-1",
      day_no: 2,
      progress_label: "2/5",
      status: "active",
      current_item_index: 2,
      planned_amount: 100,
      system_generated_amount: 90,
      manual_added_amount: 10,
      effective_amount: 100,
      has_manual_add: true,
      day_planned_amount: 300,
      day_system_generated_amount: 260,
      day_manual_added_amount: 40,
      day_effective_amount: 300,
      manual_added_item_count: 2,
      latest_manual_add_operator_id: "operator-h5-member-auth",
      latest_manual_add_at: "2026-06-24T06:00:00Z",
      current_product_id: "item-2",
      current_product_name: "Starter Product B",
      current_product_amount: 30,
      current_product_origin: "system_generated",
      total_real_recharge_amount: 120,
      total_withdraw_amount: 20,
      estimated_reward_amount: 15,
      claimed_at: "2026-06-24T00:00:00Z",
      completed_at: null,
    });
  });

  it("maps camelCase monitor summary into the snake_case frontend contract", () => {
    const summary = normalizeTaskMonitorSummaryResponse({
      totalCount: 3,
      manualAddCount: 2,
      totalPlannedAmount: 300,
      totalManualAddedAmount: 30,
      totalEffectiveAmount: 330,
      totalRealRechargeAmount: 150,
      totalWithdrawAmount: 40,
    });

    expect(summary).toEqual({
      total_count: 3,
      manual_add_count: 2,
      total_planned_amount: 300,
      total_manual_added_amount: 30,
      total_effective_amount: 330,
      total_real_recharge_amount: 150,
      total_withdraw_amount: 40,
    });
  });

  it("maps camelCase alert events into the snake_case frontend contract", () => {
    const event = normalizeTaskMonitorAlertEventResponse({
      id: "evt-1",
      accountId: "acct-1",
      alertRuleId: "rule-1",
      packageId: "pkg-1",
      userId: "user-1",
      publicUserId: "pub-u1",
      status: "open",
      priority: "high",
      ruleName: "High Amount",
      currentValue: 150,
      thresholdValue: 130,
      soundEnabled: true,
      triggeredAt: "2026-06-24T00:00:00Z",
      acknowledgedAt: null,
      acknowledgedBy: null,
      resolvedAt: null,
      resolvedBy: null,
    });

    expect(event).toEqual({
      id: "evt-1",
      account_id: "acct-1",
      alert_rule_id: "rule-1",
      package_id: "pkg-1",
      user_id: "user-1",
      public_user_id: "pub-u1",
      status: "open",
      priority: "high",
      rule_name: "High Amount",
      current_value: 150,
      threshold_value: 130,
      sound_enabled: true,
      triggered_at: "2026-06-24T00:00:00Z",
      acknowledged_at: null,
      acknowledged_by: null,
      resolved_at: null,
      resolved_by: null,
    });
  });
});
