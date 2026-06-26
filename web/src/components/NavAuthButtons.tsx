"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";

export function NavAuthButtons({ isAuthed }: { isAuthed: boolean }) {
  const router = useRouter();

  async function handleSignOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/");
    router.refresh();
  }

  if (isAuthed) {
    return (
      <>
        <Button href="/dashboard" variant="ghost" size="sm">
          Dashboard
        </Button>
        <Button variant="primary" size="sm" onClick={handleSignOut}>
          Sign out
        </Button>
      </>
    );
  }

  return (
    <>
      <Button href="/login" variant="ghost" size="sm">
        Log in
      </Button>
      <Button href="/signup" variant="primary" size="sm">
        Start free
      </Button>
    </>
  );
}
