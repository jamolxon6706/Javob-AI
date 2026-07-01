import { describe, expect, it, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OtpStep } from "@/components/auth/otp-step";
import { renderWithIntl } from "./test-utils";

const baseProps = {
  phone: "+998901234567",
  devOtp: null,
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onResend: vi.fn().mockResolvedValue(undefined),
  onChangeNumber: vi.fn(),
  pending: false,
  serverError: null,
};

describe("OtpStep", () => {
  it("masks the phone number in the subtitle", () => {
    renderWithIntl(<OtpStep {...baseProps} />);
    expect(screen.getByText(/998 90 123 \*\* 67/)).toBeInTheDocument();
  });

  it("strips non-digit characters and caps length at 6", async () => {
    renderWithIntl(<OtpStep {...baseProps} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "12a3456789");
    expect(input).toHaveValue("123456");
  });

  it("shows the dev OTP hint when provided", () => {
    renderWithIntl(<OtpStep {...baseProps} devOtp="654321" />);
    expect(screen.getByText(/654321/)).toBeInTheDocument();
  });

  it("disables resend during the cooldown window", () => {
    renderWithIntl(<OtpStep {...baseProps} />);
    const resendButton = screen.getByText(/Qayta yuborish: \d+s/);
    expect(resendButton).toBeDisabled();
  });

  it("calls onChangeNumber when 'change number' is clicked", async () => {
    const onChangeNumber = vi.fn();
    renderWithIntl(<OtpStep {...baseProps} onChangeNumber={onChangeNumber} />);
    fireEvent.click(screen.getByText("Raqamni o'zgartirish"));
    expect(onChangeNumber).toHaveBeenCalledOnce();
  });

  it("calls onSubmit with a valid 6-digit code", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithIntl(<OtpStep {...baseProps} onSubmit={onSubmit} />);

    await userEvent.type(screen.getByRole("textbox"), "123456");
    fireEvent.click(screen.getByRole("button", { name: /Tasdiqlash/ }));

    expect(onSubmit).toHaveBeenCalledWith("123456");
  });

  it("renders a server error when provided", () => {
    renderWithIntl(<OtpStep {...baseProps} serverError="Kod noto'g'ri" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Kod noto'g'ri");
  });
});
