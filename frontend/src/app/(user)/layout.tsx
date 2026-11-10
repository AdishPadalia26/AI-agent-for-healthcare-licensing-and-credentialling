import type { Metadata } from "next";
import Sidebar from "../../components/sidebar";

export const metadata: Metadata = {
  title: "FormAI",
  description: "Upload a provider document and complete credentialing forms",
};

export default function UserLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      {children}
    </div>
  );
}
