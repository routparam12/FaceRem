import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "FaceAttend — facial attendance for modern teams",
  description:
    "Multi-tenant facial attendance: enroll faces once, check in with a glance, and keep shift-aware records per organization.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem('faceattend_theme')==='flat'){document.documentElement.setAttribute('data-theme','flat')}}catch(e){}`,
          }}
        />
      </head>
      <body className="relative min-h-dvh">
        <div className="liquid-bg" aria-hidden="true">
          <div className="liquid-blob liquid-blob-1" />
          <div className="liquid-blob liquid-blob-2" />
          <div className="liquid-blob liquid-blob-3" />
        </div>
        {children}
      </body>
    </html>
  );
}
