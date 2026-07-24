import { render, screen } from "@testing-library/react";

import { App } from "../src/app/App";

describe("StyleCapture shell", () => {
  it("offers camera and gallery capture without leaving the wardrobe", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "我的衣橱" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "拍一件" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "从相册选" })).toBeInTheDocument();
  });
});
