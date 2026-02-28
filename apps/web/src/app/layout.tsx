import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "App",
  description: "Built with the project template",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
