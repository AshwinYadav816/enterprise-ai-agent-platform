import { redirect } from "next/navigation";

// Phase 2 decides between /chat and /login from the auth state; Phase 7 adds a landing page.
export default function Home() {
  redirect("/login");
}
