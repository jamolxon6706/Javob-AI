import { describe, expect, it, vi } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PhoneStep } from "@/components/auth/phone-step";
import { renderWithIntl } from "./test-utils";

describe("PhoneStep", () => {
  it("disables submit until a valid phone number is entered", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithIntl(<PhoneStep onSubmit={onSubmit} pending={false} serverError={null} />);

    const button = screen.getByRole("button");
    expect(button).toBeDisabled();

    const input = screen.getByRole("textbox");
    await userEvent.type(input, "901234567");

    expect(button).not.toBeDisabled();
  });

  it("calls onSubmit with the normalized phone number", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithIntl(<PhoneStep onSubmit={onSubmit} pending={false} serverError={null} />);

    await userEvent.type(screen.getByRole("textbox"), "901234567");
    fireEvent.click(screen.getByRole("button"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith("+998901234567"));
  });

  it("shows a validation error after blurring an invalid number", async () => {
    const onSubmit = vi.fn();
    renderWithIntl(<PhoneStep onSubmit={onSubmit} pending={false} serverError={null} />);

    const input = screen.getByRole("textbox");
    await userEvent.type(input, "123");
    fireEvent.blur(input);

    expect(
      screen.getByText("Telefon raqamini to'g'ri formatda kiriting")
    ).toBeInTheDocument();
  });

  it("renders a server error when provided", () => {
    renderWithIntl(
      <PhoneStep onSubmit={vi.fn()} pending={false} serverError="Server down" />
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Server down");
  });

  it("disables submit while pending", async () => {
    renderWithIntl(<PhoneStep onSubmit={vi.fn()} pending={true} serverError={null} />);
    await userEvent.type(screen.getByRole("textbox"), "901234567");
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
