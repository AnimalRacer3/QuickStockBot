export type SubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "incomplete"
  | "incomplete_expired"
  | "unpaid"
  | null;

export function isAccessAllowed(status: string | null | undefined): boolean {
  return status === "trialing" || status === "active";
}

export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case "trialing":
      return "Free Trial";
    case "active":
      return "Active";
    case "past_due":
      return "Payment Past Due";
    case "canceled":
      return "Canceled";
    case "incomplete":
    case "incomplete_expired":
      return "Incomplete";
    case "unpaid":
      return "Unpaid";
    default:
      return "No Subscription";
  }
}
