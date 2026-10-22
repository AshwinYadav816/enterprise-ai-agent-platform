import type { Metadata } from "next";

import { ReportsView } from "@/components/tools/tool-views";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return <ReportsView />;
}
