import { type AnchorHTMLAttributes, type ButtonHTMLAttributes } from "react";

type BaseProps = {
  variant?: "primary" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
};

type ButtonProps = BaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };
type AnchorProps = BaseProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

type Props = ButtonProps | AnchorProps;

const variants = {
  primary:
    "bg-primary text-bg font-semibold hover:bg-primary-hover active:scale-95 shadow-[0_0_20px_rgba(16,217,138,0.3)] hover:shadow-[0_0_28px_rgba(16,217,138,0.45)]",
  ghost: "text-ink-muted hover:text-ink hover:bg-white/5 border border-transparent",
  outline: "border border-border-strong text-ink hover:border-primary/50 hover:text-primary",
};

const sizes = {
  sm: "px-4 py-2 text-sm rounded-lg",
  md: "px-5 py-2.5 text-sm rounded-xl",
  lg: "px-7 py-3.5 text-base rounded-xl",
};

export function Button({ variant = "primary", size = "md", ...props }: Props) {
  const className = [
    "inline-flex items-center justify-center gap-2 transition-all duration-150 cursor-pointer select-none",
    variants[variant],
    sizes[size],
    (props as ButtonProps).className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  if ("href" in props && props.href !== undefined) {
    const { href, ...rest } = props as AnchorProps;
    return (
      <a href={href} {...rest} className={className}>
        {rest.children}
      </a>
    );
  }

  const { children, ...rest } = props as ButtonProps;
  return (
    <button {...rest} className={className}>
      {children}
    </button>
  );
}
