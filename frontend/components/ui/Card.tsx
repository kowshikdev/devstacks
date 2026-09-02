import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  subtle?: boolean;
  interactive?: boolean;
}

export function Card({ subtle, interactive, className, ...rest }: CardProps) {
  return (
    <div
      className={[
        "card",
        subtle ? "card--subtle" : "",
        interactive ? "card--interactive" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    />
  );
}

export function CardHeader({
  title,
  actions,
  className,
}: {
  title: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={["card__header", className ?? ""].filter(Boolean).join(" ")}>
      <h2 className="card__title">{title}</h2>
      {actions ? <div className="row gap-2">{actions}</div> : null}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={["card__body", className ?? ""].filter(Boolean).join(" ")} {...rest} />;
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={["card__footer", className ?? ""].filter(Boolean).join(" ")} {...rest} />;
}
