import "./globals.css";
import Link from "next/link";
import HeaderNav from "../components/HeaderNav";

export const metadata = {
  title: "Elite Events",
  description: "Plataforma de eventos e ingressos",
};

export const viewport = {
  colorScheme: "dark",
  themeColor: "#0d0f12",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            ELITE<span>EVENTS</span>
          </Link>
          <HeaderNav />
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
