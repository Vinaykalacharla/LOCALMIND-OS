import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import SecurityGate from "@/components/SecurityGate";
import SecurityProvider from "@/components/SecurityProvider";
import ToastProvider from "@/components/ToastProvider";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "LocalMind OS",
  description: "Personal Offline AI Brain"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <ToastProvider>
          <SecurityProvider>
            <div className="relative min-h-screen text-ink">
              <div className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute left-1/2 top-0 h-[18rem] w-[48rem] -translate-x-1/2 rounded-full bg-sky-400/8 blur-3xl" />
              </div>
              <div className="relative flex min-h-screen">
                <Sidebar />
                <div className="relative flex min-h-screen min-w-0 flex-1 flex-col">
                  <Header />
                  <main className="relative flex-1 px-4 pb-10 pt-6 sm:px-6 lg:px-8">
                    <div className="mx-auto w-full max-w-[1600px] animate-rise">
                      <SecurityGate>{children}</SecurityGate>
                    </div>
                  </main>
                </div>
              </div>
            </div>
          </SecurityProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
