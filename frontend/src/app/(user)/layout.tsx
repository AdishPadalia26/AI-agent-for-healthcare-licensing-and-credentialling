import type { Metadata } from "next";
import Sidebar from "../../components/sidebar";

export const metadata: Metadata = {
  title: "Upload CV",
  description: "Upload CV to fill the form",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <Sidebar />
          {children}
        </div>
      </body>
    </html>
  );
}
