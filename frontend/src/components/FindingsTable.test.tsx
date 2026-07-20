import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import FindingsTable from "./FindingsTable";
import type { Finding } from "../api";

const findings: Finding[] = [
  {
    rule_id: "SOX-302",
    status: "fail",
    severity: "Critical",
    confidence: 0.9,
    explanation: "Missing certification",
    evidence: [{ chunk_id: "c1", quote: "no cert found" }],
  },
];

describe("FindingsTable", () => {
  it("renders findings with severity", () => {
    render(<FindingsTable findings={findings} reportId="r1" />);
    expect(screen.getByText("SOX-302")).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("drills down into evidence on click", () => {
    render(<FindingsTable findings={findings} reportId="r1" />);
    fireEvent.click(screen.getByText("SOX-302"));
    expect(screen.getByText(/no cert found/)).toBeInTheDocument();
  });
});
