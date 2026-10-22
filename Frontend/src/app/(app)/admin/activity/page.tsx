import type { Metadata } from "next";

import { ActivityView } from "@/components/admin/activity-table";

export const metadata: Metadata = { title: "Activity · Admin" };

export default function Page() {
  return <ActivityView />;
}
