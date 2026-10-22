import type { Metadata } from "next";

import { EmailView } from "@/components/tools/tool-views";

export const metadata: Metadata = { title: "Email" };

export default function Page() {
  return <EmailView />;
}
