import RoleGuard from "../../components/RoleGuard";

export default function GateLayout({ children }: { children: React.ReactNode }) {
  return <RoleGuard allowedRoles={["gate"]}>{children}</RoleGuard>;
}
