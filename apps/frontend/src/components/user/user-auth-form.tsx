import { IconArrowRight, IconBrandGoogle, IconMapPin } from "@tabler/icons-react";
import Link from "next/link";

const loginErrorMessages: Record<string, string> = {
  account_conflict: "這個 Google 帳戶已經綁定其他一般使用者資料，請使用原本的 Google 帳戶登入。",
  google_login_failed: "Google 登入沒有完成，請稍後再試。",
};

export function UserAuthForm({ error }: { error?: string }) {
  // Translate only known callback codes; never expose raw OAuth/provider errors to users.
  // 只轉換已知 callback 錯誤碼，避免把 OAuth 或供應商原始錯誤直接顯示給使用者。
  const errorMessage = error ? loginErrorMessages[error] : undefined;

  return (
    <main className="user-auth-page">
      <section className="user-auth-panel" aria-labelledby="user-auth-title">
        <Link className="user-auth-brand" href="/" aria-label="回到 BiteMap 探索">
          <span>B</span>
          <strong>BiteMap</strong>
        </Link>
        <div>
          <p className="user-auth-eyebrow">
            <IconMapPin aria-hidden="true" /> 台灣，從一口開始
          </p>
          <h1 id="user-auth-title">歡迎回到 BiteMap</h1>
          <p>登入後收藏喜歡的店，和朋友一起找到下一間值得吃的地方。</p>
        </div>
        <div className="user-auth-form">
          {errorMessage ? (
            <p className="user-auth-feedback is-error" role="alert">
              {errorMessage}
            </p>
          ) : null}
          <a
            className="button button--primary user-auth-submit user-auth-google-button"
            href="/api/v1/auth/google/start"
          >
            <IconBrandGoogle aria-hidden="true" />
            使用 Google 登入
            <IconArrowRight aria-hidden="true" />
          </a>
          <p className="user-auth-anonymous">登入後即可探索地圖、餐廳與 BiteMap 的完整功能。</p>
        </div>
        <small className="user-auth-privacy">
          登入資訊由 Google 驗證，BiteMap 只建立自己的安全 Session，不保存 Google Token。
        </small>
      </section>
      <aside className="user-auth-context" aria-hidden="true">
        <div className="user-auth-map-lines" />
        <div className="user-auth-pin user-auth-pin--one">B</div>
        <div className="user-auth-pin user-auth-pin--two">B</div>
        <div className="user-auth-context-copy">
          <span>好味道，總在地圖的某個角落。</span>
          <small>從巷弄小店到城市餐桌，BiteMap 陪你找到下一個想一起吃的地方。</small>
        </div>
      </aside>
    </main>
  );
}
