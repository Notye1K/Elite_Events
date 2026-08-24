import RoleGuard from "../../../components/RoleGuard";

export default function CheckoutLayout({ children }: { children: React.ReactNode }) {
  return <RoleGuard allowedRoles={["client"]}>{children}</RoleGuard>;
}
