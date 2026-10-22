import type { Metadata } from "next";

import { GenerationList } from "@/components/tools/generation-list";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return <GenerationList />;
}
