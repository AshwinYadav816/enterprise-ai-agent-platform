import type { Metadata } from "next";

import { GenerationDetail } from "@/components/tools/generation-detail";

export const metadata: Metadata = { title: "History" };

export default function GenerationPage() {
  return <GenerationDetail />;
}
