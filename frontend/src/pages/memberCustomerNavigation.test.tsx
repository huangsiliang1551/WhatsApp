import { describe, expect, it } from "vitest";

import { CustomersPage } from "./CustomersPage";
import { OperationsCenterPage } from "./OperationsCenterPage";
import { TasksPage } from "./TasksPage";

describe("platform page exports", () => {
  it("exports customers page", () => {
    expect(CustomersPage).toBeTruthy();
  });

  it("exports operations center page", () => {
    expect(OperationsCenterPage).toBeTruthy();
  });

  it("exports tasks page", () => {
    expect(TasksPage).toBeTruthy();
  });
});
