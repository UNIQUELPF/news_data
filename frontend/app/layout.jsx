import "./globals.css";

export const metadata = {
  title: "全球政治经济数据库",
  description: "全球政治经济数据库前端控制台"
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
