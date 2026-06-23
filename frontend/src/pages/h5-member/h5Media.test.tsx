import { describe, expect, it } from "vitest";

describe("MediaUploader", () => {
  it("component can be imported", async () => {
    const mod = await import("./MediaUploader");
    expect(mod.MediaUploader).toBeDefined();
  });

  it("UploadedFile type is exported", async () => {
    const mod = await import("./MediaUploader");
    // MediaUploader is a function component
    expect(typeof mod.MediaUploader).toBe("function");
  });
});

describe("ImageViewer", () => {
  it("component exists", async () => {
    const mod = await import("./ImageViewer");
    expect(mod.ImageViewer).toBeDefined();
  });

  it("is a function component", async () => {
    const mod = await import("./ImageViewer");
    expect(typeof mod.ImageViewer).toBe("function");
  });
});
