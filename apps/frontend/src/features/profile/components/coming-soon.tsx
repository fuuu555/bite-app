import Link from "next/link";
import { IconArrowLeft, IconMap2 } from "@tabler/icons-react";

type ComingSoonProps = {
  title: string;
  description: string;
  backHref?: string;
  reference?: string;
};

export function ComingSoon({ title, description, backHref = "/", reference }: ComingSoonProps) {
  return (
    <main className="coming-soon">
      <div className="coming-soon__brand" aria-hidden="true">
        B
      </div>
      <h1>{title}</h1>
      <p>{description}</p>
      {reference ? <small>店家識別碼：{reference}</small> : null}
      <div className="coming-soon__actions">
        <Link className="button button--secondary" href={backHref}>
          <IconArrowLeft aria-hidden="true" />
          返回
        </Link>
        <Link className="button button--primary" href="/map">
          <IconMap2 aria-hidden="true" />
          開啟地圖
        </Link>
      </div>
    </main>
  );
}
