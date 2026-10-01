import type { SVGProps } from "react";

type IconName = "restaurant" | "cuisine" | "logout" | "map" | "plus" | "back" | "user";

const paths: Record<IconName, React.ReactNode> = {
  restaurant: <path d="M4 5h16v14H4zM8 9h8M8 13h5" />,
  cuisine: <path d="M5 4v7a3 3 0 0 0 3 3V4m-3 4h3m8-4v16m0-16c3 2 3 7 0 9" />,
  logout: <path d="M10 5H5v14h5m4-4 4-3-4-3m4 3H9" />,
  map: <path d="m3 6 5-2 8 3 5-2v13l-5 2-8-3-5 2zm5-2v13m8-10v13" />,
  plus: <path d="M12 5v14M5 12h14" />,
  back: <path d="m15 5-7 7 7 7" />,
  user: <path d="M5 20a7 7 0 0 1 14 0M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />,
};

export function Icon({ name, ...props }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
