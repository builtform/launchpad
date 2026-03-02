import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "{{PROJECT_NAME}}",
  description: "{{PROJECT_DESCRIPTION}}",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
