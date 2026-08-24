"use client";
import { useState } from "react";
import { api, saveSession } from "../../lib/api";
import { useRouter } from "next/navigation";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("login");
  const [role, setRole] = useState("client");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  async function submit(e: any) {
    e.preventDefault();
    setError("");
    try {
      const data =
        mode === "login"
          ? await api("/auth/login", {
              method: "POST",
              body: JSON.stringify({ email, password }),
            })
          : await api("/auth/register", {
              method: "POST",
              body: JSON.stringify({ name, email, password, role }),
            });
      saveSession(data);
      router.push(
        role === "gate" || data.user.role === "gate"
          ? "/gate"
          : data.user.role === "organizer"
            ? "/organizer"
            : "/events",
      );
    } catch (err: any) {
      setError(err.message);
    }
  }
  return (
    <div style={{ maxWidth: 520, margin: "40px auto" }}>
      <div className="card">
        <div className="eyebrow">Acesso</div>
        <h1>{mode === "login" ? "Entrar" : "Criar usuário"}</h1>
        <form className="form" onSubmit={submit}>
          {mode !== "login" && (
            <label>
              Nome
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={120}
              />
            </label>
          )}
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label>
            Senha
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === "login" ? 1 : 6}
              maxLength={72}
            />
          </label>
          {mode !== "login" && (
            <label>
              Papel
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="client">Cliente</option>
                <option value="organizer">Organizador</option>
                <option value="gate">Portaria</option>
              </select>
            </label>
          )}
          {error && <div className="status bad">{error}</div>}
          <button className="btn primary">
            {mode === "login" ? "Entrar" : "Registrar"}
          </button>
        </form>
        <button
          className="btn ghost"
          style={{ marginTop: 12 }}
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Quero criar um usuário" : "Já tenho acesso"}
        </button>
      </div>
    </div>
  );
}
