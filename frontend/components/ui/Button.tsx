import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "default" | "primary" | "danger" | "invisible" | "contrast";
type Size = "sm" | "md" | "lg";

interface CommonProps {
  variant?: Variant;
  size?: Size;
  block?: boolean;
  loading?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  children?: ReactNode;
  className?: string;
}

function classes({ variant = "default", size = "md", block, loading, className }: CommonProps) {
  return [
    "btn",
    variant !== "default" ? `btn--${variant}` : "",
    size !== "md" ? `btn--${size}` : "",
    block ? "btn--block" : "",
    loading ? "btn--loading" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
}

export type ButtonProps = CommonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className">;

export function Button({
  variant,
  size,
  block,
  loading,
  leadingIcon,
  trailingIcon,
  children,
  className,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={classes({ variant, size, block, loading, className })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
}

export type ButtonLinkProps = CommonProps & { href: string } & Omit<
    AnchorHTMLAttributes<HTMLAnchorElement>,
    "children" | "className" | "href"
  >;

/** The same visual button, rendered as a link when the action is navigation. */
export function ButtonLink({
  variant,
  size,
  block,
  leadingIcon,
  trailingIcon,
  children,
  className,
  href,
  ...rest
}: ButtonLinkProps) {
  const isExternal = href.startsWith("http") || href.startsWith("mailto:");
  const content = (
    <>
      {leadingIcon}
      {children}
      {trailingIcon}
    </>
  );
  const cls = classes({ variant, size, block, className });

  if (isExternal) {
    return (
      <a className={cls} href={href} {...rest}>
        {content}
      </a>
    );
  }
  return (
    <Link className={cls} href={href} {...rest}>
      {content}
    </Link>
  );
}

export type IconButtonProps = {
  icon: ReactNode;
  label: string;
  bordered?: boolean;
  className?: string;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className">;

export function IconButton({ icon, label, bordered, className, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      className={["icon-btn", bordered ? "icon-btn--bordered" : "", className ?? ""]
        .filter(Boolean)
        .join(" ")}
      aria-label={label}
      title={label}
      {...rest}
    >
      {icon}
    </button>
  );
}
