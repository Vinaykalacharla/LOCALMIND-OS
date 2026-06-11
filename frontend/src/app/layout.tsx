import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import SecurityGate from "@/components/SecurityGate";
import SecurityProvider from "@/components/SecurityProvider";
import ToastProvider from "@/components/ToastProvider";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "LocalMind OS",
  description: "Personal Offline AI Brain",
  icons: {
    icon: "/favicon.svg"
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ToastProvider>
          <SecurityProvider>
            <div className="relative flex min-h-screen w-full">
              <Sidebar />
              <div className="relative flex min-h-screen min-w-0 flex-1 flex-col">
                <Header />
                <main className="relative flex-1 px-4 py-8 sm:px-6 lg:px-8">
                  <div className="mx-auto w-full max-w-[1600px] animate-rise">
                    <SecurityGate>{children}</SecurityGate>
                  </div>
                </main>
              </div>
            </div>
          </SecurityProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
