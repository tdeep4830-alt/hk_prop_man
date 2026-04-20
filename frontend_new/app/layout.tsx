import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PropMan AI — 香港物業管理 AI 法律顧問",
  description:
    "基於《建築物管理條例》Cap. 344 及土地審裁處判例的香港物業管理 AI 法律問答系統",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-HK" suppressHydrationWarning>
      <body className="antialiased bg-white">
        {children}
      </body>
    </html>
  );
}
