"use client";

import { useEffect } from "react";
import { Outfit } from "next/font/google";
import "@/styles/globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en" className={outfit.variable} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 py-12 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary font-display text-sm font-bold text-primary-foreground">
            ESN
          </div>
          <div className="max-w-md">
            <h1 className="font-display text-xl font-semibold">Critical error</h1>
            <p className="mt-2 text-pretty text-sm text-muted-foreground">
              The application hit a fatal error. Try reloading the page. If it keeps happening, contact support.
            </p>
          </div>
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
