import RoleGuard from "../../components/RoleGuard";

export default function OrganizerLayout({ children }: { children: React.ReactNode }) {
  return <RoleGuard allowedRoles={["organizer"]}>{children}</RoleGuard>;
}
