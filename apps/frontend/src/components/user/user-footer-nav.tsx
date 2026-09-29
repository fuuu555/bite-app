"use client";

import {
  IconCompass,
  IconMap2,
  IconMessageCircle,
  IconUser,
  IconUsersGroup,
  type Icon,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type FooterItem = {
  href: string;
  label: string;
  icon: Icon;
};

const footerItems: FooterItem[] = [
  { href: "/", label: "探索", icon: IconCompass },
  { href: "/map", label: "地圖", icon: IconMap2 },
  { href: "/meals", label: "約飯", icon: IconUsersGroup },
  { href: "/chat", label: "聊天室", icon: IconMessageCircle },
  { href: "/profile", label: "個人", icon: IconUser },
];

export function UserFooterNav() {
  const pathname = usePathname();

  return (
    <footer className="user-footer">
      <nav className="user-footer__nav" aria-label="主要功能">
        {footerItems.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const ItemIcon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={active ? "is-active" : undefined}
              aria-current={active ? "page" : undefined}
            >
              <ItemIcon aria-hidden="true" stroke={1.8} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </footer>
  );
}
