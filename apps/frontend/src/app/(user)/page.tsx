import Link from "next/link";
import { IconMap2 } from "@tabler/icons-react";

export default function ExplorePage() {
  return (
    <main className="user-home">
      <div className="user-home__brand" aria-label="BiteMap">
        <span aria-hidden="true">B</span>
        <strong>BiteMap</strong>
      </div>
      <section className="user-home__content" aria-labelledby="explore-title">
        <h1 id="explore-title">探索功能準備中</h1>
        <p>完整探索與推薦會在後續階段加入。現在可以先從地圖查看附近已發布的店家。</p>
        <Link className="button button--primary user-home__action" href="/map">
          <IconMap2 aria-hidden="true" />
          開啟地圖
        </Link>
      </section>
    </main>
  );
}
