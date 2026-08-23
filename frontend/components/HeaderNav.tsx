"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getUser, type SessionUser } from "../lib/api";
import UserMenu from "./UserMenu";

export default function HeaderNav() {
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    function updateUser() {
      setUser(getUser());
    }

    updateUser();
    window.addEventListener("auth-changed", updateUser);
    window.addEventListener("storage", updateUser);

    return () => {
      window.removeEventListener("auth-changed", updateUser);
      window.removeEventListener("storage", updateUser);
    };
  }, []);

  return (
    <nav>
      <Link href="/events">Eventos</Link>
      {user?.role === "client" && (
        <Link href="/tickets">Meus ingressos</Link>
      )}
      {user?.role === "organizer" && (
        <Link href="/organizer">Organizador</Link>
      )}
      {user?.role === "gate" && <Link href="/gate">Portaria</Link>}
      <UserMenu user={user} />
    </nav>
  );
}
