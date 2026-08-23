import RoleGuard from "../../components/RoleGuard";

export default function TicketsLayout({ children }: { children: React.ReactNode }) {
  return <RoleGuard allowedRoles={["client"]}>{children}</RoleGuard>;
}
