"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearSession, type SessionUser } from "../lib/api";

const roleLabels: Record<string, string> = {
  client: "Cliente",
  organizer: "Organizador",
  gate: "Portaria",
};

export default function UserMenu({ user }: { user: SessionUser | null }) {
  const [open, setOpen] = useState(false);

  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  function logout() {
    clearSession();
    setOpen(false);

    router.push("/login");
    router.refresh();
  }

  if (!user) {
    return <Link href="/login">Entrar</Link>;
  }

  return (
    <div className="user-menu" ref={menuRef}>
      <button
        type="button"
        className="user-menu-trigger"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="user-avatar">{user.name.charAt(0).toUpperCase()}</span>

        <span
          className={`user-menu-arrow ${open ? "open" : ""}`}
          aria-hidden="true"
        >
          ▾
        </span>
      </button>

      {open && (
        <div className="user-menu-dropdown" role="menu">
          <div className="user-menu-info">
            <strong>{user.name}</strong>
            <span>{user.email}</span>
          </div>

          <div className="user-menu-role">
            {roleLabels[user.role] ?? user.role}
          </div>

          <div className="user-menu-divider" />

          <button type="button" className="user-menu-logout" onClick={logout}>
            Sair
          </button>
        </div>
      )}
    </div>
  );
}
