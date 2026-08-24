"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, getUser, type SessionUser } from "../lib/api";

type Role = SessionUser["role"];

export default function RoleGuard({
  allowedRoles,
  children,
}: {
  allowedRoles: Role[];
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const allowedRolesKey = allowedRoles.join(",");

  useEffect(() => {
    const allowedRoleSet = new Set(allowedRolesKey.split(","));

    function checkAccess() {
      const user = getUser();
      const token = getToken();

      if (!user || !token) {
        setAuthorized(false);
        router.replace("/login");
        return;
      }

      if (!allowedRoleSet.has(user.role)) {
        setAuthorized(false);
        router.replace("/events");
        return;
      }

      setAuthorized(true);
    }

    checkAccess();
    window.addEventListener("auth-changed", checkAccess);
    window.addEventListener("storage", checkAccess);

    return () => {
      window.removeEventListener("auth-changed", checkAccess);
      window.removeEventListener("storage", checkAccess);
    };
  }, [allowedRolesKey, router]);

  if (!authorized) {
    return <div className="card">Verificando permissão…</div>;
  }

  return children;
}
