import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../src/App";

describe("App", () => {
  it("renders the upload-first CFD workbench", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "AI CFD Workbench" })).toBeInTheDocument();
    expect(screen.getByText("Drop STEP, STL, Gmsh mesh, or OpenFOAM ZIP")).toBeInTheDocument();
    expect(screen.getByLabelText(/Velocity/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start CFD run/i })).toBeDisabled();
    expect(screen.getByText(/Runner:/i)).toBeInTheDocument();
  });
});
