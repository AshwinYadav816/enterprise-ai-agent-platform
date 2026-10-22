import type { Metadata } from "next";

import { AdminDashboard } from "@/components/admin/dashboard";

export const metadata: Metadata = { title: "Dashboard · Admin" };

export default function Page() {
  return <AdminDashboard />;
}
