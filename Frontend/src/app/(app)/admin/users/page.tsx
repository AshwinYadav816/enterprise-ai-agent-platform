import type { Metadata } from "next";

import { UsersView } from "@/components/admin/users-table";

export const metadata: Metadata = { title: "Users · Admin" };

export default function Page() {
  return <UsersView />;
}
