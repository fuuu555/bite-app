"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AdminApiError, adminApi } from "@/lib/admin-api";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await adminApi("/session", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.replace("/admin/restaurants");
    } catch (caught) {
      setError(
        caught instanceof AdminApiError && caught.status === 401
          ? "電子郵件或密碼不正確。"
          : "目前無法登入，請確認 API 已啟動後再試一次。",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand">
          <span>B</span>
          BiteMap
        </div>
        <div>
          <h1 id="login-title">管理員登入</h1>
          <p>管理料理分類、店家座標與發布狀態。</p>
        </div>
        <form onSubmit={submit} className="login-form">
          <label>
            電子郵件
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            密碼
            <input
              type="password"
              autoComplete="current-password"
              minLength={6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {error ? (
            <p className="form-message is-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="button button--primary" type="submit" disabled={submitting}>
            {submitting ? "登入中…" : "登入管理後台"}
          </button>
        </form>
      </section>
      <aside className="login-context" aria-hidden="true">
        <div className="login-map-lines" />
        <div className="login-pin">B</div>
        <p>可靠的店家資料，從人工確認開始。</p>
      </aside>
    </main>
  );
}
